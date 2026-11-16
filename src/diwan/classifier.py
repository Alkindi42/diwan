from ollama import ChatResponse, chat
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from diwan.initiative_loader import Initiative

DEFAULT_MODEL = "qwen3:8b"

SYSTEM_PROMPT = """
You are a timesheet classifier.

Your job is to interpret one daily work log and convert it into structured timesheet entries using only the initiatives and tasks provided in the input catalog.

The catalog is the source of truth. Never invent an initiative, task, or task key that is not present in the catalog.

## Classification

A daily log may contain one or multiple distinct work activities.

Identify the meaningful work activities described in the log and classify each one into:

- exactly one task key from the provided catalog (which identifies its initiative)
- a duration in minutes
- the numbered note line(s) describing that activity

Choose the initiative first based on the purpose and context of the work.

Then choose the task that best represents the actual work performed within that initiative.

Return its catalog key, not a task name or a numeric Saviom identifier.

Classify according to the actual purpose and outcome of the work, not isolated keywords.

For example, contextual words such as "meeting", "helped", "worked with", or a person's name must not override the nature of the work itself.

If a discussion or meeting is primarily about performing technical work, classify the technical work rather than automatically treating it as coordination.

When a classification is ambiguous, make the most plausible choice from the provided catalog. Always choose from the available catalog and never invent a fallback value.

## Activity separation

Treat clearly distinct pieces of work as separate activities when they differ in purpose, initiative, or task.

A single sentence or bullet may contain multiple activities and may therefore produce multiple entries when necessary.

Several related actions that represent one continuous piece of work may remain a single activity.

Do not intentionally aggregate unrelated activities.

Downstream code may aggregate entries that resolve to the same date, initiative, and task.

Each note line is prefixed with its original line number in square brackets.
Return source_lines with the line number(s) that contributed to each activity.
Use the same line number for multiple activities from one line; include all
relevant line numbers when an activity spans multiple lines. Never invent a
line number or copy/paraphrase the note text in the output.

## Duration

If an explicit duration is provided, preserve it and convert it to minutes.

Examples:

- 2h → 120 minutes
- 1h → 60 minutes
- 1h30 → 90 minutes
- 45 minutes → 45 minutes

Tolerate obvious spelling mistakes in duration expressions when their meaning is clear.

If no duration is provided, estimate a reasonable duration from the described work.

Estimated durations must:

- be positive
- be expressed in minutes
- use 15-minute increments
- remain plausible for the activity described

Do not invent unnecessarily precise durations such as 22, 37, or 53 minutes.

Do not force the daily total to match a predetermined number of working hours unless such a constraint is explicitly provided in the input.

## Catalog constraints

For every output entry:

- return exactly one task key from the provided catalog
- return duration_minutes as a positive integer
- return at least one source line number from the provided note

Python resolves task keys to Saviom identifiers after classification. Do not output dates or numeric identifiers.

## Output

Return only the requested structured output.

Do not include explanations, reasoning, markdown, comments, or additional text outside the structured response.
"""


class ConfigModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        str_min_length=1,
        str_strip_whitespace=True,
    )


class ClassifiedEntry(ConfigModel):
    date: str
    task_value: PositiveInt
    initiative_value: PositiveInt
    duration_minutes: PositiveInt
    source_lines: list[PositiveInt] = Field(default_factory=list)


class CatalogActivity(ConfigModel):
    task_key: str
    duration_minutes: PositiveInt
    source_lines: list[PositiveInt] = Field(min_length=1)


class CatalogResult(ConfigModel):
    entries: list[CatalogActivity]


def _catalog(initiatives: list[Initiative]) -> tuple[str, dict[str, tuple[int, int]]]:
    """Present the catalog as readable choices; keep Saviom IDs in Python."""
    lines = []
    choices: dict[str, tuple[int, int]] = {}

    for initiative in initiatives:
        lines.append(f"Initiative: {initiative.name}")
        if initiative.description:
            lines.append(f"  {initiative.description.strip()}")
        for task in initiative.tasks:
            key = f"t{len(choices) + 1}"
            choices[key] = (initiative.saviom_value, task.saviom_value)
            lines.append(f"  {key}: {task.name}")
            if task.description:
                lines.append(f"    {task.description.strip()}")

    if not choices:
        raise ValueError("The initiative catalog contains no tasks")
    return "\n".join(lines), choices


def classify(
    notes: dict[str, str], initiatives: list[Initiative], model: str = DEFAULT_MODEL
) -> list[ClassifiedEntry]:
    if not notes:
        return []

    catalog, choices = _catalog(initiatives)
    entries: list[ClassifiedEntry] = []
    for date, note in notes.items():
        numbered_lines = {
            number: line
            for number, line in enumerate(note.splitlines(), start=1)
            if line.strip()
        }
        if not numbered_lines:
            continue

        # The model selects catalog keys and note line numbers, never Saviom IDs.
        schema = CatalogResult.model_json_schema()
        activity_schema = schema["$defs"]["CatalogActivity"]["properties"]
        activity_schema["task_key"]["enum"] = list(choices)
        activity_schema["source_lines"]["items"]["enum"] = list(numbered_lines)
        numbered_note = "\n".join(
            f"[{number}] {line}" for number, line in numbered_lines.items()
        )
        prompt = (
            f"Available initiatives and tasks:\n{catalog}\n\n"
            f"Note dated {date}:\n{numbered_note}"
        )
        response: ChatResponse = chat(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            format=schema,
            options={"temperature": 0},
            think=True,
        )

        if response.message.content is None:
            raise ValueError("Ollama returned an empty response")

        for activity in CatalogResult.model_validate_json(
            response.message.content
        ).entries:
            selected = choices.get(activity.task_key)
            if selected is None:
                raise ValueError(
                    f"Ollama returned unknown task key {activity.task_key!r}"
                )
            for number in activity.source_lines:
                if number not in numbered_lines:
                    raise ValueError(
                        f"Ollama returned unknown source line {number} for {date}"
                    )
            initiative_value, task_value = selected
            entries.append(
                ClassifiedEntry(
                    date=date,
                    initiative_value=initiative_value,
                    task_value=task_value,
                    duration_minutes=activity.duration_minutes,
                    source_lines=sorted(set(activity.source_lines)),
                )
            )

    return aggregate_entries(entries)


def aggregate_entries(
    entries: list[ClassifiedEntry],
) -> list[ClassifiedEntry]:
    """Aggregate classified entries by date, initiative, and task."""

    aggregated: dict[tuple[str, int, int], ClassifiedEntry] = {}

    for entry in entries:
        key = (entry.date, entry.initiative_value, entry.task_value)
        if key not in aggregated:
            aggregated[key] = entry.model_copy(deep=True)
        else:
            current = aggregated[key]
            current.duration_minutes += entry.duration_minutes
            current.source_lines = sorted(
                set(current.source_lines + entry.source_lines)
            )

    return list(aggregated.values())
