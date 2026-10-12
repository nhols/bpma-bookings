"""Read a booking sheet image with an LLM."""

import datetime as dt
import os

from pydantic_ai import Agent, BinaryContent, ModelRetry, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel

from bpma.sheet import Sheet, problems
from bpma.store import Extraction

# Chosen with the evals on 12 Oct 2026 (see evals/results/): both read all 16 sheets right 3 times out of 3,
# for about 1p a sheet. The fallback answers if the main model fails.
MODEL = os.environ.get("BPMA_MODEL", "google:gemini-3.8-flash")
FALLBACK_MODEL = os.environ.get("BPMA_FALLBACK_MODEL", "google:gemini-3.5-flash")

INSTRUCTIONS = """\
You read images of the athletics track booking sheet for Battersea Park Millennium Arena.
Copy every row of every table on the sheet. Some sheets have two tables side by side.

- Dates: take the year from the heading. A row like "5 MAY - 8 MAY" has first_day 5 May and last_day 8 May.
- weekday_as_printed, time_as_printed and event_type: copy them exactly as printed, typos included.
  If a cell repeats the same event type once per time slot, write it once.
- slots: when the track is booked, as 24-hour times.
  - Times often leave out am/pm on the first part: "12 - 6:30pm" is 12:00-18:30 and "7-9PM" is 19:00-21:00.
  - Codes are explained in the key at the bottom of the sheet. If there is no key, use
    AM = 08:30-12:30, PM = 13:00-17:00, EVE = 17:00-21:00, ALL DAY = 08:30-16:30.
  - Combined codes such as "AM - PM", "PM - EVE" or "ALL DAY & EVE" are one slot,
    from the start of the first code to the end of the last.
  - Two separate times in one row are two slots.
  - If the time is "TBA", "-" or anything else that isn't a time, leave slots empty.
"""

agent: Agent[None, Sheet] = Agent(
    output_type=Sheet, instructions=INSTRUCTIONS, retries=2, defer_model_check=True, name="sheet_reader"
)


@agent.output_validator
def _check(ctx: RunContext[None], sheet: Sheet) -> Sheet:
    """Ask the model to double-check anything that looks wrong, such as a date on the wrong weekday, once.

    The sheet itself could be wrong, so the second reading is accepted whatever it says.
    """
    if (found := problems(sheet)) and ctx.retry == 0:
        raise ModelRetry(
            "These look wrong. Check them against the sheet. If the sheet really says this, keep it as it is:\n"
            + "\n".join(found)
        )
    return sheet


def extract(image: bytes, media_type: str, model: str | Model | None = None) -> Extraction:
    """Read a sheet. Pass `model` to use only that model (the evals do); otherwise MODEL with FALLBACK_MODEL."""
    result = agent.run_sync(
        ["Read this booking sheet.", BinaryContent(data=image, media_type=media_type)],
        model=model or FallbackModel(MODEL, FALLBACK_MODEL),
    )
    return Extraction(
        model=result.response.model_name or "unknown",
        extracted_at=dt.datetime.now(dt.UTC),
        sheet=result.output,
        problems=problems(result.output),
    )
