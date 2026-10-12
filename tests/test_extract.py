from conftest import row, sheet
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from bpma.extract import extract
from bpma.sheet import Sheet

# The sheet says Tuesday, but 13 October 2025 was a Monday: a mistake on the sheet, or a misread year.
WRONG = sheet(row("2025-10-13", ("12:00", "18:30")).model_copy(update={"weekday_as_printed": "TUESDAY"}))
RIGHT = sheet(row("2026-10-13", ("12:00", "18:30")))


def model_reading(*readings: Sheet) -> tuple[FunctionModel, list[int]]:
    """A fake model that gives these readings in turn, and a list that counts its calls."""
    calls: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        reading = readings[min(len(calls), len(readings) - 1)]
        calls.append(1)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, reading.model_dump(mode="json"))])

    return FunctionModel(respond), calls


def test_a_misreading_is_corrected_after_one_double_check() -> None:
    model, calls = model_reading(WRONG, RIGHT)
    extraction = extract(b"image", "image/jpeg", model=model)
    assert len(calls) == 2
    assert extraction.sheet == RIGHT
    assert extraction.problems == []


def test_a_sheet_that_is_itself_wrong_is_accepted_after_one_double_check() -> None:
    model, calls = model_reading(WRONG)
    extraction = extract(b"image", "image/jpeg", model=model)
    assert len(calls) == 2  # asked once to double-check, then accepted rather than failing the sync
    assert extraction.sheet == WRONG
    assert len(extraction.problems) == 1
