"""Write classified entries to Saviom via Playwright.

All Saviom-specific knowledge (URLs, selectors, form layout) is isolated
in this module. Nothing here ever submits a timesheet: entries are filled
and saved, but submission is always left to the user.

Grid layout of frmTimesheet.aspx (one page = one week, Mon-Sun):
- ``selGrid,{row},5``  initiative dropdown (value "0" = empty row)
- ``selGrid,{row},6``  task dropdown, rebuilt when the initiative changes
- ``txtGrid,{row},{8..14}``  day cells (decimal hours), Monday = column 8
- ``TSRGRIDHD,{col}``  day header, its ``tag`` attribute holds e.g. "Oct 19 2026"
- ``#btnPrev`` / ``#btnNext``  week navigation, ``#lblWeekRange``  current week
- ``#btnTSSave``  save, followed by a Confirm dialog (``ConformYES*``);
  validation errors show as Alert dialogs (``AlertOk*``)
"""

import re
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from diwan.classifier import ClassifiedEntry
from diwan.paths import DIWAN_DIR

PROFILE_DIR = DIWAN_DIR / "browser-profile"

LOGIN_TIMEOUT_MS = 5 * 60 * 1000
WEEK_NAV_TIMEOUT_MS = 15 * 1000
MAX_WEEK_NAV_CLICKS = 40
TASK_OPTIONS_TIMEOUT_MS = 5 * 1000

INITIATIVE_COL = 5
TASK_COL = 6
DAY_COLS = range(8, 15)
EMPTY_SELECT_VALUES = {"", "0", "-1"}

WEEK_RANGE_FORMAT = "%b %d %Y"
ENTRY_DATE_FORMAT = "%d-%m-%Y"


@dataclass
class WriteReport:
    written: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@contextmanager
def saviom_session(timesheet_url: str) -> Iterator[Page]:
    """Open the Saviom timesheet page in an authenticated session.

    Uses a persistent browser profile for the SSO session. Clicks the
    Saviom Login link when needed, then waits for the timesheet grid.
    Further SSO interaction, if required, is left to the user.
    """
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(PROFILE_DIR, headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(timesheet_url)

            _wait_for_timesheet(page)
            page.wait_for_load_state("networkidle")
            yield page
        finally:
            context.close()


def _wait_for_timesheet(page: Page) -> None:
    """Click the Saviom Login link once, then wait for the actual grid.

    The timesheet URL alone is not sufficient: the browser can reach it
    before Saviom finishes loading or redirects to its login page.
    """
    login_link = page.get_by_role("link", name=re.compile(r"^log\s*in$", re.IGNORECASE))
    deadline = time.monotonic() + LOGIN_TIMEOUT_MS / 1000
    clicked_login = False
    prompted = False

    while time.monotonic() < deadline:
        if page.locator("#lblWeekRange").is_visible():
            return

        if not clicked_login and login_link.count() == 1 and login_link.is_visible():
            print("Clicking the Saviom Login link...")
            login_link.click()
            clicked_login = True
        elif not prompted and not clicked_login:
            print("Waiting for My Timesheet; complete SSO in the browser if needed...")
            prompted = True

        page.wait_for_timeout(250)

    raise TimeoutError(
        "My Timesheet did not load within five minutes; "
        "check the browser for an SSO prompt or an unexpected login page."
    )


def write_entries(
    classified_entries: list[ClassifiedEntry], timesheet_url: str
) -> None:
    """Fill and save the Saviom timesheet with the given entries.

    Never submits. Existing non-empty day cells are never overwritten;
    conflicts are reported for manual resolution instead.
    """
    if not classified_entries:
        print("No entries to write.")
        return

    weeks: dict[date, list[tuple[ClassifiedEntry, date]]] = defaultdict(list)
    for entry in classified_entries:
        entry_date = _parse_entry_date(entry.date)
        weeks[_monday_of(entry_date)].append((entry, entry_date))

    report = WriteReport()

    with saviom_session(timesheet_url) as page:
        for monday in sorted(weeks):
            print(f"Week of {monday}...")
            _goto_week(page, monday)
            day_columns = _day_columns(page)
            week_report = WriteReport()

            for entry, entry_date in weeks[monday]:
                _write_entry(page, entry, entry_date, day_columns, week_report)

            report.problems.extend(week_report.problems)
            if not week_report.written:
                continue

            problem = _save(page)
            if problem:
                report.problems.append(
                    f"Week of {monday}: save failed ({problem}); "
                    f"{len(week_report.written)} filled cell(s) not confirmed saved"
                )
                break  # Stop processing further weeks after a failed save.

            report.written.extend(week_report.written)

    _print_report(report)


# --- orchestration helpers ---------------------------------------------------


def _write_entry(
    page: Page,
    entry: ClassifiedEntry,
    entry_date: date,
    day_columns: dict[date, int],
    report: WriteReport,
) -> None:
    label = (
        f"{entry.date} | initiative {entry.initiative_value} "
        f"/ task {entry.task_value} ({_to_hours(entry.duration_minutes)}h)"
    )

    col = day_columns.get(entry_date)
    if col is None:
        report.problems.append(f"{label}: date not visible on the current week page")
        return

    row = _find_row(page, entry.initiative_value, entry.task_value)
    if row is None:
        report.problems.append(f"{label}: no empty grid row available")
        return

    problem = _select_initiative_and_task(
        page, row, entry.initiative_value, entry.task_value
    )
    if problem:
        report.problems.append(f"{label}: {problem}")
        return

    problem = _fill_day_cell(page, row, col, entry.duration_minutes)
    if problem:
        report.problems.append(f"{label}: {problem}")
        return

    report.written.append(f"{label} -> row {row}, column {col}")


def _parse_entry_date(raw: str) -> date:
    try:
        return datetime.strptime(raw, ENTRY_DATE_FORMAT).date()
    except ValueError:
        raise ValueError(
            f"Cannot parse entry date {raw!r}; expected format dd-mm-yyyy"
        ) from None


def _monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _to_hours(duration_minutes: int) -> str:
    """Convert minutes to the decimal-hour format the day cells accept."""
    return f"{duration_minutes / 60:.2f}".rstrip("0").rstrip(".")


# --- grid interaction --------------------------------------------------------


def _current_week_start(page: Page) -> date:
    week_range = page.locator("#lblWeekRange").inner_text()
    start = week_range.split(" - ")[0].strip()
    return datetime.strptime(start, WEEK_RANGE_FORMAT).date()


def _goto_week(page: Page, target_monday: date) -> None:
    for _ in range(MAX_WEEK_NAV_CLICKS):
        current = _current_week_start(page)
        if current == target_monday:
            return

        if page.evaluate("() => window.mblnDataChanged === true"):
            raise RuntimeError(
                "Unsaved changes detected before week navigation; "
                "aborting to avoid discarding them."
            )

        button = "#btnPrev" if target_monday < current else "#btnNext"
        previous_range = page.locator("#lblWeekRange").inner_text().strip()
        page.locator(button).click()
        page.wait_for_function(
            "(previous) =>"
            " document.getElementById('lblWeekRange').textContent.trim() !== previous",
            arg=previous_range,
            timeout=WEEK_NAV_TIMEOUT_MS,
        )

    raise RuntimeError(f"Could not reach week of {target_monday}")


def _day_columns(page: Page) -> dict[date, int]:
    """Map each visible day to its grid column using the header `tag` dates."""
    columns = {}
    for col in DAY_COLS:
        tag = page.locator(f'[id="TSRGRIDHD,{col}"]').get_attribute("tag")
        if tag:
            columns[datetime.strptime(tag.strip(), WEEK_RANGE_FORMAT).date()] = col
    return columns


def _find_row(page: Page, initiative_value: int, task_value: int) -> int | None:
    """Return the row for (initiative, task), reusing an existing row or
    taking the first empty one. None when no row is available."""
    first_empty = None

    for row in range(1, 100):
        initiative_select = page.locator(f'[id="selGrid,{row},{INITIATIVE_COL}"]')
        if initiative_select.count() == 0:
            break

        current_initiative = initiative_select.input_value().strip()
        if current_initiative in EMPTY_SELECT_VALUES:
            if first_empty is None:
                first_empty = row
            continue

        if int(current_initiative) == initiative_value:
            task_select = page.locator(f'[id="selGrid,{row},{TASK_COL}"]')
            current_task = task_select.input_value().strip()
            if (
                current_task not in EMPTY_SELECT_VALUES
                and int(current_task) == task_value
            ):
                return row

    return first_empty


def _select_initiative_and_task(
    page: Page, row: int, initiative_value: int, task_value: int
) -> str | None:
    """Select initiative then task on a row. Returns a problem or None."""
    initiative_select = page.locator(f'[id="selGrid,{row},{INITIATIVE_COL}"]')
    task_select = page.locator(f'[id="selGrid,{row},{TASK_COL}"]')

    if initiative_select.input_value().strip() != str(initiative_value):
        initiative_select.select_option(str(initiative_value))

    # The task options are rebuilt client-side when the initiative changes.
    task_option = task_select.locator(f'option[value="{task_value}"]')
    try:
        task_option.wait_for(state="attached", timeout=TASK_OPTIONS_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        return (
            f"task {task_value} not available under initiative {initiative_value} "
            f"on row {row}"
        )

    if task_select.input_value().strip() != str(task_value):
        task_select.select_option(str(task_value))

    return None


def _fill_day_cell(page: Page, row: int, col: int, duration_minutes: int) -> str | None:
    """Write decimal hours into a day cell. Returns a problem or None."""
    cell = page.locator(f'[id="txtGrid,{row},{col}"]')
    hours = _to_hours(duration_minutes)

    existing = cell.input_value().strip()
    if existing not in EMPTY_SELECT_VALUES:
        try:
            is_zero = float(existing) == 0.0
        except ValueError:
            is_zero = False
        if not is_zero:
            return f"cell already contains {existing!r}; left untouched"

    cell.fill(hours)
    cell.press("Tab")

    try:
        actual = float(cell.input_value().strip())
    except ValueError:
        return f"could not read back cell value {cell.input_value()!r}"
    if abs(actual - float(hours)) > 0.005:
        return f"cell shows {actual}h after writing {hours}h"

    return None


# --- save & dialogs ----------------------------------------------------------


def _save(page: Page) -> str | None:
    """Click Save and confirm the dialog. Returns a problem or None."""
    page.locator("#btnTSSave").click()

    yes_button = page.locator("button[id^='ConformYES']").first
    try:
        yes_button.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeoutError:
        alert = _dismiss_alert(page)
        return alert or "save confirmation dialog did not appear"

    yes_button.click()
    page.wait_for_load_state("networkidle")
    page.locator("#preloader").wait_for(state="hidden", timeout=30 * 1000)

    return _dismiss_alert(page)


def _dismiss_alert(page: Page) -> str | None:
    """Dismiss a Saviom Alert dialog if one is shown; return its message."""
    ok_button = page.locator("button[id^='AlertOk']").first
    if ok_button.count() == 0 or not ok_button.is_visible():
        return None

    message = page.locator("div[id^='dialogboxbody']").first.inner_text().strip()
    ok_button.click()
    return message or "unknown Saviom alert"


def _print_report(report: WriteReport) -> None:
    count = len(report.written)
    print(f"\nSaved {count} {'cell' if count == 1 else 'cells'}.")
    for line in report.written:
        print(f"  + {line}")

    if report.problems:
        print("\nNeeds attention:")
        for line in report.problems:
            print(f"  ! {line}")
