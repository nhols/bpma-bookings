"""What a booking sheet says, and what it means for the calendar."""

import datetime as dt
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

LONDON = ZoneInfo("Europe/London")
WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class TimeSlot(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: dt.time = Field(description="24-hour start time.")
    end: dt.time = Field(description="24-hour end time.")


class Row(BaseModel):
    """One row of the booking table, as read by the model."""

    first_day: dt.date = Field(description="The date in the DATE column. For a range like '5 MAY - 8 MAY', 5 May.")
    last_day: dt.date = Field(description="The last date of a range like '5 MAY - 8 MAY'. Otherwise same as first_day.")
    weekday_as_printed: str = Field(description="The DAY column exactly as printed, typos included.")
    time_as_printed: str = Field(description="The TIME column exactly as printed.")
    slots: list[TimeSlot] = Field(description="When the track is booked. Empty if the time is TBA, '-' or not a time.")
    event_type: str = Field(description="The EVENT TYPE column exactly as printed.")


class Sheet(BaseModel):
    """Everything on one booking sheet image."""

    title: str = Field(description="The heading, e.g. 'Athletics Track Bookings October 2026'.")
    rows: list[Row]


class Booking(BaseModel):
    """One calendar event: a single day and time slot."""

    model_config = ConfigDict(frozen=True)

    day: dt.date
    slot: TimeSlot | None  # None means all day
    title: str
    time_as_printed: str
    sheet_id: str
    image_name: str  # e.g. "image.png", in data/sheets/<sheet_id>/

    @property
    def starts_at(self) -> dt.datetime:
        start = self.slot.start if self.slot else dt.time(0, 0)
        return dt.datetime.combine(self.day, start, tzinfo=LONDON)


def problems(sheet: Sheet) -> list[str]:
    """Things that are definitely wrong with a reading of a sheet. An empty list means it looks fine."""
    found: list[str] = []
    if not sheet.rows:
        found.append("No rows were read from the sheet.")
    for row in sheet.rows:
        label = f"Row for {row.first_day:%d %B %Y}"
        # Sheets misspell weekdays ("WEDNEDAY", "SATUDAY") but the first three letters have always been right.
        if row.weekday_as_printed.strip().upper()[:3] != WEEKDAYS[row.first_day.weekday()]:
            found.append(
                f"{label}: the DAY column says {row.weekday_as_printed!r} but {row.first_day:%d %B %Y} "
                f"is a {row.first_day:%A}. Check the date and the year."
            )
        if row.last_day < row.first_day:
            found.append(f"{label}: last_day {row.last_day} is before first_day.")
        for slot in row.slots:
            if slot.end <= slot.start:
                found.append(f"{label}: slot {slot.start:%H:%M}-{slot.end:%H:%M} ends before it starts.")
    return found


def bookings(sheet: Sheet, sheet_id: str, image_name: str) -> list[Booking]:
    """Turn a sheet into calendar bookings: one per day per time slot, or one all-day booking if there are no times."""
    result: list[Booking] = []
    for row in sheet.rows:
        title = " ".join(row.event_type.split()).capitalize()  # "EXCLUSIVE  TRACK BOOKING" -> "Exclusive track booking"
        printed = row.time_as_printed.strip()
        if not row.slots and printed not in ("", "-"):
            title = f"{title} ({printed})"  # e.g. "Exclusive track booking (TBA)"
        slots: list[TimeSlot | None] = list(row.slots) or [None]
        day = row.first_day
        while day <= row.last_day:
            for slot in slots:
                result.append(
                    Booking(
                        day=day,
                        slot=slot,
                        title=title,
                        time_as_printed=printed,
                        sheet_id=sheet_id,
                        image_name=image_name,
                    )
                )
            day += dt.timedelta(days=1)
    return result
