import datetime as dt
import itertools

from bpma.gcal import Event
from bpma.sheet import Booking, Row, Sheet, TimeSlot


class FakeCalendar:
    """Stands in for Google Calendar."""

    def __init__(self) -> None:
        self.events: dict[str, Event] = {}
        self.fail_on_create: int | None = None  # make the nth create call fail
        self._ids = itertools.count(1)
        self._creates = 0

    def events_starting_after(self, moment: dt.datetime) -> list[Event]:
        return [event for event in self.events.values() if event.starts_at > moment]

    def delete(self, event: Event) -> None:
        del self.events[event.id]

    def create(self, booking: Booking) -> Event:
        self._creates += 1
        if self._creates == self.fail_on_create:
            raise ConnectionError("Calendar API unavailable")
        event = Event(id=f"event{next(self._ids)}", summary=booking.title, starts_at=booking.starts_at)
        self.events[event.id] = event
        return event


def row(
    day: str, *slots: tuple[str, str], time: str = "", event: str = "EXCLUSIVE TRACK BOOKING", last_day: str = ""
) -> Row:
    first = dt.date.fromisoformat(day)
    return Row(
        first_day=first,
        last_day=dt.date.fromisoformat(last_day) if last_day else first,
        weekday_as_printed=f"{first:%A}".upper(),
        time_as_printed=time,
        slots=[TimeSlot(start=dt.time.fromisoformat(a), end=dt.time.fromisoformat(b)) for a, b in slots],
        event_type=event,
    )


def sheet(*rows: Row) -> Sheet:
    return Sheet(title="Athletics Track Bookings", rows=list(rows))
