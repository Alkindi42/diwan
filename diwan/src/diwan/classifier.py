from collections import defaultdict

from ollama import ChatResponse, chat
from pydantic import BaseModel, ConfigDict, PositiveInt

from diwan.initiative_loader import Initiative

SYSTEM_PROMPT = """
You are a timesheet classifier.

Your job is to interpret one daily work log and convert it into structured timesheet entries using only the initiatives and tasks provided in the input catalog.

The catalog is the source of truth. Never invent an initiative, task, identifier, or relationship that is not present in the catalog.

## Classification

A daily log may contain one or multiple distinct work activities.

Identify the meaningful work activities described in the log and classify each one into:

- exactly one initiative
- exactly one task belonging to that initiative
- a duration in minutes

Choose the initiative first based on the purpose and context of the work.

Then choose the task that best represents the actual work performed within that initiative.

Only select tasks that belong to the selected initiative.

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

- use only initiative values present in the provided catalog
- use only task values present in the provided catalog
- ensure the selected task belongs to the selected initiative
- return duration_minutes as a positive integer

The human-readable names in the catalog are context for classification.

The numeric values are the identifiers that must be returned.

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


class ClassifiedResult(ConfigModel):
    entries: list[ClassifiedEntry]


# TODO: send context instead of initiatives
def classify(
    notes: dict[str, str], initiatives: list[Initiative]
) -> list[ClassifiedEntry]:

    entries: list[ClassifiedEntry] = []
    for date, note in notes.items():
        prompt = f"""
Available initiatives and tasks:
{initiatives}

Note dated {date}:
{note}
    """
        response: ChatResponse = chat(
            model="qwen3:8b",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            format=ClassifiedResult.model_json_schema(),
            options={"temperature": 0},
            think=True,
        )

        if response.message.content is None:
            raise ValueError("Ollama returned an empty response")

        daily_entries = ClassifiedResult.model_validate_json(
            response.message.content
        ).entries

        for daily_entry in daily_entries:
            daily_entry.date = date

        entries.extend(daily_entries)

    return aggregate_entries(entries)


def aggregate_entries(
    entries: list[ClassifiedEntry],
) -> list[ClassifiedEntry]:
    """Aggregate classified entries by date, initiative, and task."""

    aggregated = defaultdict(int)

    for entry in entries:
        key = (entry.date, entry.initiative_value, entry.task_value)
        aggregated[key] += entry.duration_minutes

    aggregated_entries = []

    for (date, initiative_value, task_value), duration in aggregated.items():
        aggregated_entries.append(
            ClassifiedEntry(
                date=date,
                task_value=task_value,
                duration_minutes=duration,
                initiative_value=initiative_value,
            )
        )

    return aggregated_entries
