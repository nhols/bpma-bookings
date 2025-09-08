import datetime
from datetime import time
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FromToTime(BaseModel):
    start: time
    end: time

    @field_validator("start", "end", mode="after")
    @classmethod
    def strip_tz_info(cls, v: time):
        return v.replace(tzinfo=None)


class Booking(BaseModel):
    day: Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] | None = None
    date: datetime.date = Field(description="The full date of the booking")
    time: FromToTime | str = Field(
        description="Either a start and end time or a string describing the duration e.g. 'ALL DAY'"
    )
    event_type: str | None = None
    any_other_info: str | None = None

    @property
    def booking_id(self) -> str:
        """A unique identifier for the booking, based on its JSON representation."""
        return self.model_dump_json()


class Bookings(BaseModel):
    bookings: list[Booking]

    @property
    def range(self) -> int:
        """
        Get the number of days between the first and last booking.
        """
        if not self.bookings:
            return 0

        from_date = min(booking.date for booking in self.bookings)
        to_date = max(booking.date for booking in self.bookings)
        return (to_date - from_date).days + 1
