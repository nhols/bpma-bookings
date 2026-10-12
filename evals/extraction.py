"""How well do models read booking sheets? Scores them against the hand-checked data/sheets/*/expected.json.

    uv run --env-file .env evals/extraction.py                     # the default model
    uv run --env-file .env evals/extraction.py --models google:gemini-3.8-flash google:gemini-3.1-flash-lite
    uv run evals/report.py                                         # see the results

Each run is saved to evals/results/. A row counts as right only if its dates, time slots and event type all match;
the weekday and time as printed are ignored because they're copied for the audit trail, not used.
"""

import argparse
import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext
from results import Attempt, EvalRun, compare, save
from tenacity import retry_if_exception, stop_after_attempt, wait_fixed

from bpma.extract import MODEL, extract
from bpma.sheet import Sheet
from bpma.store import Store

STORE = Store(Path(__file__).parent.parent / "data")


@dataclass
class RowsMatch(Evaluator[str, Sheet]):
    def evaluate(self, ctx: EvaluatorContext[str, Sheet]) -> dict[str, float | bool]:
        assert ctx.expected_output is not None
        missed, wrong = compare(ctx.expected_output, ctx.output)
        expected_rows = len(ctx.expected_output.rows)
        return {
            "rows_right": (expected_rows - missed.total()) / expected_rows,
            "rows_wrong": wrong.total(),
            "perfect": not missed and not wrong,
        }


def worth_retrying(error: BaseException) -> bool:
    """Overloaded (503) or over the per-minute limit (429). Not out of the day's quota: waiting won't help."""
    return isinstance(error, ModelHTTPError) and error.status_code in (429, 503) and "PerDay" not in str(error.body)


def code_version() -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()

    dirty = git("status", "--porcelain", "src/bpma/extract.py", "src/bpma/sheet.py")
    return git("rev-parse", "--short", "HEAD") + ("-dirty" if dirty else "")


def repeat_number(name: str) -> int:
    """pydantic-evals names repeated cases like "case name [2/3]"."""
    match = re.search(r"\[(\d+)/\d+\]$", name)
    return int(match[1]) if match else 1


def evaluate(model: str, repeat: int, concurrency: int) -> EvalRun:
    cases = [
        Case(name=f"{asset_id[:8]} {STORE.source(asset_id).filename}", inputs=asset_id, expected_output=sheet)
        for asset_id, sheet in STORE.expected().items()
    ]

    def read(asset_id: str) -> Sheet:
        return extract(*STORE.image(asset_id), model=model).sheet

    ran_at = dt.datetime.now(dt.UTC)
    report = Dataset[str, Sheet](name="sheet_reading", cases=cases, evaluators=[RowsMatch()]).evaluate_sync(
        read,
        name=model,
        max_concurrency=concurrency,
        repeat=repeat,
        progress=False,
        retry_task={"retry": retry_if_exception(worth_retrying), "wait": wait_fixed(30), "stop": stop_after_attempt(4)},
    )
    attempts = [
        Attempt(
            asset_id=case.inputs,
            repeat=repeat_number(case.name),
            output=case.output,
            error=None,
            seconds=case.task_duration,
            cost=case.metrics.get("cost"),
        )
        for case in report.cases
    ]
    attempts += [
        Attempt(
            asset_id=failure.inputs,
            repeat=repeat_number(failure.name),
            output=None,
            error=failure.error_message,
            seconds=0,
            cost=None,
        )
        for failure in report.failures
    ]
    return EvalRun(model=model, ran_at=ran_at, code_version=code_version(), attempts=attempts)


def is_perfect(attempt: Attempt) -> bool:
    if attempt.output is None:
        return False
    missed, wrong = compare(STORE.expected()[attempt.asset_id], attempt.output)
    return not missed and not wrong


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=[MODEL])
    parser.add_argument("--repeat", type=int, default=3, help="Read each sheet this many times.")
    parser.add_argument("--concurrency", type=int, default=8, help="Readings to run at once.")
    args = parser.parse_args()

    for model in args.models:
        run = evaluate(model, args.repeat, args.concurrency)
        path = save(run)
        perfect = sum(map(is_perfect, run.attempts))
        cost = sum(a.cost or 0 for a in run.attempts)
        print(f"{model}: {perfect}/{len(run.attempts)} readings perfect, ${cost:.3f}. Saved {path.name}")
    print("See the details with: uv run evals/report.py")


if __name__ == "__main__":
    main()
