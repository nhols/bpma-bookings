"""Turn the saved eval results into one HTML page: a summary of every run, then where each reading went wrong.

uv run evals/report.py             # writes evals/report.html and opens it
"""

import argparse
import webbrowser
from collections import Counter
from html import escape
from pathlib import Path

from results import Attempt, EvalRun, RowKey, compare, load_all, row_key

from bpma.sheet import Sheet
from bpma.store import Store

STORE = Store(Path(__file__).parent.parent / "data")
OUT = Path(__file__).parent / "report.html"

STYLE = """
:root { --bg: #fafafa; --fg: #1d1d1f; --muted: #6e6e73; --line: #e2e2e6; --good: #1a7f37; --bad: #cf222e;
        --good-bg: #dafbe1; --bad-bg: #ffebe9; --card: #ffffff; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #151517; --fg: #ececf1; --muted: #9a9aa2; --line: #2e2e33; --good: #3fb950; --bad: #f85149;
          --good-bg: #12261a; --bad-bg: #2d1416; --card: #1c1c1f; }
}
body { background: var(--bg); color: var(--fg); font: 14px/1.5 system-ui, sans-serif; margin: 0; }
main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 18px; margin: 40px 0 8px; } h3 { font-size: 15px; margin: 0; }
.muted { color: var(--muted); }
table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { padding: 6px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
th { font-weight: 600; color: var(--muted); font-size: 12px; }
td.num { text-align: right; }
.scroll { overflow-x: auto; }
a { color: inherit; }
.ok { color: var(--good); } .no { color: var(--bad); font-weight: 600; }
.diff { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; margin: 12px 0;
        display: grid; grid-template-columns: 160px minmax(0, 1fr); gap: 14px; }
.diff img { width: 160px; border-radius: 4px; border: 1px solid var(--line); }
pre { margin: 8px 0 0; font: 12.5px/1.6 ui-monospace, Menlo, monospace; overflow-x: auto; }
.missed { background: var(--bad-bg); display: block; } .extra { background: var(--good-bg); display: block; }
"""


def describe(key: RowKey) -> str:
    first, last, slots, event = key
    days = f"{first:%a %d %b %Y}" + (f" to {last:%a %d %b}" if last != first else "")
    times = ", ".join(f"{start:%H:%M}-{end:%H:%M}" for start, end in slots) or "no times"
    return f"{days:<30} {times:<26} {event}"


def mistakes(attempt: Attempt, expected: Sheet) -> tuple[Counter[RowKey], Counter[RowKey]] | None:
    """(missed, wrong) rows, or None if the model call failed."""
    return compare(expected, attempt.output) if attempt.output else None


def is_perfect(attempt: Attempt, expected: Sheet) -> bool:
    found = mistakes(attempt, expected)
    return found is not None and not found[0] and not found[1]


def run_id(run: EvalRun) -> str:
    return f"{run.model.split(':')[-1]}-{run.ran_at:%Y%m%d%H%M%S}"


def summary_row(run: EvalRun, expected: dict[str, Sheet]) -> str:
    attempts = run.attempts
    perfect = sum(is_perfect(a, expected[a.asset_id]) for a in attempts)
    failed = sum(a.output is None for a in attempts)
    rows_total = sum(len(expected[a.asset_id].rows) for a in attempts)
    rows_missed = sum(m[0].total() for a in attempts if (m := mistakes(a, expected[a.asset_id])))
    rows_wrong = sum(m[1].total() for a in attempts if (m := mistakes(a, expected[a.asset_id])))
    by_sheet: dict[str, set[tuple[RowKey, ...]]] = {}
    for a in attempts:
        by_sheet.setdefault(a.asset_id, set()).add(tuple(sorted(map(row_key, a.output.rows))) if a.output else ())
    consistent = sum(len(readings) == 1 for readings in by_sheet.values())
    cost = sum(a.cost or 0 for a in attempts)
    seconds = [a.seconds for a in attempts if a.output]
    return (
        f"<tr><td><a href='#{run_id(run)}'>{escape(run.model)}</a></td>"
        f"<td>{run.ran_at:%d %b %Y %H:%M}</td><td class='muted'>{escape(run.code_version)}</td>"
        f"<td class='num'><b>{perfect}/{len(attempts)}</b> ({perfect / len(attempts):.0%})</td>"
        f"<td class='num'>{(rows_total - rows_missed) / rows_total:.1%}</td>"
        f"<td class='num'>{rows_wrong}</td><td class='num'>{failed}</td>"
        f"<td class='num'>{consistent}/{len(by_sheet)}</td>"
        f"<td class='num'>{sum(seconds) / max(len(seconds), 1):.1f}s</td>"
        f"<td class='num'>${cost:.3f}</td></tr>"
    )


def run_section(run: EvalRun, expected: dict[str, Sheet]) -> str:
    repeats = max(a.repeat for a in run.attempts)
    attempts = {(a.asset_id, a.repeat): a for a in run.attempts}
    grid, diffs = [], []
    for asset_id in sorted({a.asset_id for a in run.attempts}, key=lambda i: STORE.source(i).first_seen):
        name = f"{STORE.source(asset_id).first_seen:%d %b %Y} · {STORE.source(asset_id).filename}"
        cells = []
        for n in range(1, repeats + 1):
            attempt = attempts.get((asset_id, n))
            anchor = f"{run_id(run)}-{asset_id[:8]}-{n}"
            if attempt is None:
                cells.append("<td class='muted'>-</td>")
            elif is_perfect(attempt, expected[asset_id]):
                cells.append("<td class='ok'>✓</td>")
            else:
                found = mistakes(attempt, expected[asset_id])
                label = "error" if found is None else f"-{found[0].total()} +{found[1].total()}"
                cells.append(f"<td><a class='no' href='#{anchor}'>{label}</a></td>")
                diffs.append(diff_block(anchor, name, n, attempt, expected[asset_id]))
        grid.append(f"<tr><td>{escape(name)}</td>{''.join(cells)}</tr>")
    header = "".join(f"<th>Reading {n}</th>" for n in range(1, repeats + 1))
    return (
        f"<h2 id='{run_id(run)}'>{escape(run.model)} <span class='muted'>· {run.ran_at:%d %b %Y %H:%M}</span></h2>"
        f"<div class='scroll'><table><tr><th>Sheet</th>{header}</tr>{''.join(grid)}</table></div>"
        + ("".join(diffs) or "<p class='ok'>Every reading matched the expected rows.</p>")
    )


def diff_block(anchor: str, name: str, repeat: int, attempt: Attempt, expected: Sheet) -> str:
    image = next((STORE.root / "sheets" / attempt.asset_id).glob("image.*"))
    found = mistakes(attempt, expected)
    if found is None:
        body = f"<pre>{escape(attempt.error or 'Failed')}</pre>"
    else:
        missed, wrong = found
        lines = [(key, "missed", "-") for key in missed.elements()] + [(key, "extra", "+") for key in wrong.elements()]
        lines.sort(key=lambda line: (line[0][0], line[1] == "extra"))  # by date, expected row first
        right = len(expected.rows) - missed.total()
        body = (
            f"<p class='muted'>{right} of {len(expected.rows)} rows right. "
            "<span class='missed'>- expected but not read</span><span class='extra'>+ read but not expected</span></p>"
            "<pre>"
            + "".join(f"<span class='{css}'>{sign} {escape(describe(key))}</span>" for key, css, sign in lines)
            + "</pre>"
        )
    return (
        f"<div class='diff' id='{anchor}'><a href='{image.relative_to(OUT.parent, walk_up=True)}'>"
        f"<img src='{image.relative_to(OUT.parent, walk_up=True)}' loading='lazy' alt=''></a>"
        f"<div><h3>{escape(name)} <span class='muted'>· reading {repeat}</span></h3>{body}</div></div>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-open", action="store_true", help="Write the report without opening it.")
    args = parser.parse_args()

    runs, expected = load_all(), STORE.expected()
    columns = ["Model", "Ran", "Code", "Perfect readings", "Rows right", "Wrong rows", "Failed calls",
               "Same every time", "Time per sheet", "Cost"]  # fmt: skip
    page = (
        f"<!doctype html><meta charset='utf-8'><title>Sheet reading evals</title><style>{STYLE}</style><main>"
        "<h1>Sheet reading evals</h1>"
        f"<p class='muted'>{len(runs)} runs against {len(expected)} hand-checked sheets. Newest first. "
        "A reading is perfect when every row's dates, times and event type match.</p>"
        "<div class='scroll'><table><tr>"
        + "".join(f"<th>{c}</th>" for c in columns)
        + "</tr>"
        + "".join(summary_row(run, expected) for run in runs)
        + "</table></div>"
        + "".join(run_section(run, expected) for run in runs)
        + "</main>"
    )
    OUT.write_text(page)
    print(f"Wrote {OUT}")
    if not args.no_open:
        webbrowser.open(OUT.as_uri())


if __name__ == "__main__":
    main()
