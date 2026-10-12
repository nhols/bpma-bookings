import datetime as dt
from pathlib import Path

import pytest
from conftest import FakeCalendar, row, sheet

from bpma.page import SheetRef
from bpma.sheet import Booking, Sheet, bookings
from bpma.store import Extraction, Run, Store
from bpma.sync import NoSheetsError, sync

NOW = dt.datetime(2026, 10, 12, 15, 0, tzinfo=dt.UTC)
OCTOBER = sheet(
    row("2026-10-12", ("08:30", "12:30")),  # this morning: already past
    row("2026-10-13", ("12:00", "18:30")),
    row("2026-10-29", ("08:30", "16:30")),
)


def booking(day: str) -> Booking:
    [result] = bookings(sheet(row(day, ("10:00", "11:00"))), "old-sheet")
    return result


def ref(asset_id: str) -> SheetRef:
    return SheetRef(asset_id=asset_id, url=f"https://example.com/{asset_id}.jpg", filename=f"{asset_id}.jpg")


class Page:
    """The web page and the model: which sheets are up, and what the model reads from each."""

    def __init__(self, sheets: dict[str, Sheet]) -> None:
        self.sheets = sheets
        self.extractions = 0

    def download(self, url: str) -> bytes:
        return url.removeprefix("https://example.com/").removesuffix(".jpg").encode()

    def extract(self, image: bytes, media_type: str) -> Extraction:
        self.extractions += 1
        return Extraction(model="test", extracted_at=NOW, sheet=self.sheets[image.decode()])


def run_sync(tmp_path: Path, calendar: FakeCalendar, page: Page, now: dt.datetime = NOW, **options: bool) -> Run | None:
    return sync(
        now=now,
        sheets=[ref(asset_id) for asset_id in page.sheets],
        store=Store(tmp_path),
        calendar=calendar,
        download=page.download,
        extract=page.extract,
        **options,
    )


def test_a_new_sheet_replaces_every_future_event(tmp_path: Path) -> None:
    calendar = FakeCalendar()
    past = calendar.create(booking("2026-10-01"))
    future = calendar.create(booking("2026-10-20"))

    run = run_sync(tmp_path, calendar, Page({"oct": OCTOBER}))

    assert run is not None
    assert [e.id for e in run.deleted] == [future.id]
    assert past.id in calendar.events  # the past is never touched
    assert sorted(e.starts_at.date().isoformat() for e in calendar.events.values()) == [
        "2026-10-01",
        "2026-10-13",
        "2026-10-29",
    ]
    assert Store(tmp_path).last_run() == run


def test_nothing_happens_when_the_page_has_not_changed(tmp_path: Path) -> None:
    calendar, page = FakeCalendar(), Page({"oct": OCTOBER})
    run_sync(tmp_path, calendar, page)
    before = dict(calendar.events)

    assert run_sync(tmp_path, calendar, page) is None
    assert calendar.events == before
    assert page.extractions == 1  # each sheet is only ever read once


def test_force_rebuilds_even_when_nothing_changed(tmp_path: Path) -> None:
    calendar, page = FakeCalendar(), Page({"oct": OCTOBER})
    run_sync(tmp_path, calendar, page)

    run = run_sync(tmp_path, calendar, page, force=True)
    assert run is not None
    assert len(run.deleted) == len(run.created) == 2


def test_a_dry_run_changes_nothing(tmp_path: Path) -> None:
    calendar = FakeCalendar()
    assert run_sync(tmp_path, calendar, Page({"oct": OCTOBER}), dry_run=True) is None
    assert calendar.events == {}
    assert Store(tmp_path).last_run() is None


def test_an_empty_page_is_an_error_not_an_empty_calendar(tmp_path: Path) -> None:
    with pytest.raises(NoSheetsError):
        run_sync(tmp_path, FakeCalendar(), Page({}))


def test_a_failed_rebuild_is_redone_by_the_next_run(tmp_path: Path) -> None:
    calendar, page = FakeCalendar(), Page({"oct": OCTOBER})
    calendar.fail_on_create = 2
    with pytest.raises(ConnectionError):
        run_sync(tmp_path, calendar, page)
    assert Store(tmp_path).last_run() is None

    run_sync(tmp_path, calendar, page)
    assert sorted(e.starts_at.date().isoformat() for e in calendar.events.values()) == ["2026-10-13", "2026-10-29"]
