"""Replay 14 months of real uploads (Aug 2025 - Oct 2026) through the sync, using the hand-checked readings."""

import datetime as dt
from collections import Counter
from pathlib import Path

import pytest
from conftest import FakeCalendar

from bpma.page import SheetRef
from bpma.sheet import LONDON, problems
from bpma.store import Extraction, Store
from bpma.sync import sync

DATA = Store(Path(__file__).parent.parent / "data")

# When the set of sheets on the page changed, from the old pipeline's logs. Ids are asset id prefixes.
PAGE_HISTORY = [
    ("2025-08-30", ["accaf56f"]),  # Aug 2025
    ("2025-09-04", ["df53921f"]),  # Sep 2025
    ("2025-09-08", ["74866f51"]),  # Sep 2025, amended
    ("2025-09-11", ["3b9e1341"]),  # Sep 2025, amended again
    ("2025-09-22", ["2c7ca546"]),  # Sep-Oct 2025, overlaps Sep on 25-27 Sep
    ("2025-09-30", ["4b9223a4"]),  # Sep-Oct 2025, amended
    ("2025-11-26", ["74b938f4"]),  # Nov-Dec 2025
    ("2026-01-15", ["641ee9d3"]),  # Jan 2026
    ("2026-02-03", ["7bcba2b1"]),  # Feb 2026
    ("2026-03-03", ["02087b41"]),  # Mar 2026
    ("2026-04-10", ["dd678b18"]),  # Apr 2026
    ("2026-04-28", ["dd678b18", "e670e1c5"]),  # Apr and May 2026
    ("2026-05-22", ["e670e1c5"]),  # May 2026
    ("2026-05-27", ["bc634576", "667babc8"]),  # May 2026 re-uploaded, Jun 2026
    ("2026-05-29", ["bc634576", "d7945b68"]),  # Jun 2026 extended
    ("2026-10-12", ["9e68c66a"]),  # Oct 2026
]


def full_id(prefix: str) -> str:
    return next(asset_id for asset_id in DATA.expected() if asset_id.startswith(prefix))


def test_every_hand_checked_reading_is_valid() -> None:
    expected = DATA.expected()
    assert len(expected) == 16
    for asset_id, sheet in expected.items():
        assert problems(sheet) == [], asset_id
        assert DATA.image(asset_id)[0], asset_id
        assert asset_id in DATA.source(asset_id).url, asset_id


@pytest.fixture(scope="module")
def calendar(tmp_path_factory: pytest.TempPathFactory) -> FakeCalendar:
    calendar, store = FakeCalendar(), Store(tmp_path_factory.mktemp("data"))
    for day, prefixes in PAGE_HISTORY:
        sync(
            now=dt.datetime.combine(dt.date.fromisoformat(day), dt.time(11, 0), tzinfo=LONDON),
            sheets=[
                SheetRef(asset_id=full_id(p), url=f"https://example.com/{full_id(p)}", filename="x.jpg")
                for p in prefixes
            ],
            store=store,
            calendar=calendar,
            download=lambda url: url.rsplit("/", 1)[1].encode(),
            extract=lambda image, media_type: Extraction(
                model="hand-checked", extracted_at=dt.datetime.now(dt.UTC), sheet=DATA.expected()[image.decode()]
            ),
        )
    return calendar


def events_on(calendar: FakeCalendar, day: str) -> list[str]:
    return sorted(
        f"{e.starts_at:%H:%M} {e.summary}" for e in calendar.events.values() if e.starts_at.date().isoformat() == day
    )


def test_no_duplicate_events(calendar: FakeCalendar) -> None:
    counts = Counter((e.starts_at, e.summary) for e in calendar.events.values())
    assert [key for key, n in counts.items() if n > 1] == []


def test_amendments_replace_the_original_times(calendar: FakeCalendar) -> None:
    assert events_on(calendar, "2025-09-16") == ["07:00 Exclusive use track booking"]  # was AM
    assert events_on(calendar, "2025-09-17") == ["13:00 Exclusive use track booking"]  # was PM


def test_dates_shared_by_two_sheets_appear_once(calendar: FakeCalendar) -> None:
    assert events_on(calendar, "2025-09-25") == ["08:30 Exclusive use school booking"]


def test_an_added_row_appears(calendar: FakeCalendar) -> None:
    assert events_on(calendar, "2025-10-06") == ["18:00 Exclusive use track booking"]


def test_extended_june_sheet_ends_on_28_june_once(calendar: FakeCalendar) -> None:
    assert events_on(calendar, "2026-06-28") == ["08:30 Exclusive track booking"]


def test_the_october_sheet_is_in_the_calendar(calendar: FakeCalendar) -> None:
    october = [e for e in calendar.events.values() if e.starts_at.date() >= dt.date(2026, 10, 13)]
    assert len(october) == 10
