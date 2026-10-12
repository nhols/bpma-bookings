"""The daily sync.

The rule: the sheets on the page are the truth about the future. Whenever the set of sheets on the page changes,
delete every future event and create one for every future booking on those sheets. The past is never touched.
"""

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from bpma.gcal import Event
from bpma.page import SheetRef
from bpma.sheet import Booking, bookings
from bpma.store import Extraction, Run, Store

log = logging.getLogger(__name__)


class Calendar(Protocol):
    def events_starting_after(self, moment: dt.datetime) -> list[Event]: ...
    def delete(self, event: Event) -> None: ...
    def create(self, booking: Booking) -> Event: ...


@dataclass(frozen=True)
class Plan:
    delete: list[Event]
    create: list[Booking]


class NoSheetsError(Exception):
    """The page has no booking sheets. More likely the page changed than the track has no bookings at all."""


def make_plan(future_events: list[Event], all_bookings: list[Booking], now: dt.datetime) -> Plan:
    # Two sheets on the page at once could both list the same booking; keep one.
    unique = {(b.day, b.slot, b.title): b for b in all_bookings}
    return Plan(
        delete=[e for e in future_events if e.starts_at > now],
        create=sorted((b for b in unique.values() if b.starts_at > now), key=lambda b: b.starts_at),
    )


def sync(
    *,
    now: dt.datetime,
    sheets: list[SheetRef],
    store: Store,
    calendar: Calendar,
    download: Callable[[str], bytes],
    extract: Callable[[bytes, str], Extraction],
    force: bool = False,
    dry_run: bool = False,
) -> Run | None:
    """Bring the calendar in line with the sheets on the page. Returns what changed, or None if nothing did."""
    if not sheets:
        raise NoSheetsError("No booking sheets found on the page")

    for ref in sheets:
        if not store.has_image(ref.asset_id):
            log.info("New sheet: %s", ref.filename)
            store.save_image(ref, download(ref.url), now)
        if not store.has_extraction(ref.asset_id):
            extraction = extract(*store.image(ref.asset_id))
            if extraction.problems:
                log.warning("%s may be wrong on the sheet itself: %s", ref.filename, extraction.problems)
            store.save_extraction(ref.asset_id, extraction)

    asset_ids = [ref.asset_id for ref in sheets]
    last = store.last_run()
    if last and set(last.sheets) == set(asset_ids) and not force:
        log.info("Same sheets as the last rebuild; nothing to do")
        return None

    all_bookings = [b for asset_id in asset_ids for b in bookings(store.extraction(asset_id).sheet, asset_id)]
    plan = make_plan(calendar.events_starting_after(now), all_bookings, now)
    log.info("Plan: delete %d future events, create %d", len(plan.delete), len(plan.create))
    if dry_run:
        for event in plan.delete:
            print(f"delete  {event.starts_at:%a %d %b %Y %H:%M}  {event.summary}")
        for booking in plan.create:
            print(f"create  {booking.starts_at:%a %d %b %Y %H:%M}  {booking.title}")
        return None

    # If this fails part way, no run is saved, so the next run rebuilds again from scratch.
    for event in plan.delete:
        calendar.delete(event)
    created = [calendar.create(booking) for booking in plan.create]
    run = Run(ran_at=now, sheets=asset_ids, deleted=plan.delete, created=created)
    store.save_run(run)
    return run
