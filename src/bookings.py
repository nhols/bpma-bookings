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


class Bookings(BaseModel):
    bookings: list[Booking]
