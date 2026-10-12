"""Saved eval results: evals/results/<time>_<model>.json, one file per model per eval run."""

import datetime as dt
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from bpma.sheet import Row, Sheet

RESULTS = Path(__file__).parent / "results"

RowKey = tuple[dt.date, dt.date, tuple[tuple[dt.time, dt.time], ...], str]


class Attempt(BaseModel):
    """One reading of one sheet."""

    asset_id: str
    repeat: int  # 1, 2, 3...
    output: Sheet | None  # None if the model call failed
    error: str | None
    seconds: float
    cost: float | None  # US dollars


class EvalRun(BaseModel):
    model: str
    ran_at: dt.datetime
    code_version: str  # git commit, with "-dirty" if the prompt or schema had uncommitted changes
    attempts: list[Attempt]


def row_key(row: Row) -> RowKey:
    """What has to match for a row to count as right: dates, time slots and event type."""
    slots = tuple((slot.start, slot.end) for slot in row.slots)
    return (row.first_day, row.last_day, slots, " ".join(row.event_type.upper().split()))


def compare(expected: Sheet, actual: Sheet) -> tuple[Counter[RowKey], Counter[RowKey]]:
    """The rows the model missed, and the rows it got wrong or made up."""
    want, got = Counter(map(row_key, expected.rows)), Counter(map(row_key, actual.rows))
    return want - got, got - want


def save(run: EvalRun) -> Path:
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{run.ran_at:%Y-%m-%dT%H%M%SZ}_{run.model.split(':')[-1]}.json"
    path.write_text(run.model_dump_json(indent=1) + "\n")
    return path


def load_all() -> list[EvalRun]:
    """Every saved run, newest first."""
    return [EvalRun.model_validate_json(p.read_text()) for p in sorted(RESULTS.glob("*.json"), reverse=True)]
