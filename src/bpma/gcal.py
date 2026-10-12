"""The Google Calendar API, via a service account. The calendar belongs to this app: every event in it is ours."""

import datetime as dt
import json
import os
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
from pydantic import BaseModel, Field

from bpma.sheet import LONDON, Booking

REPO = "https://github.com/nhols/bpma-bookings"
SCOPE = "https://www.googleapis.com/auth/calendar.events"


class Event(BaseModel):
    """An event in the calendar."""

    id: str
    summary: str
    starts_at: dt.datetime


class _When(BaseModel):
    date: dt.date | None = None  # all-day events
    date_time: dt.datetime | None = Field(default=None, alias="dateTime")  # timed events

    def to_datetime(self) -> dt.datetime:
        if self.date_time:
            return self.date_time
        if self.date:
            return dt.datetime.combine(self.date, dt.time(0, 0), tzinfo=LONDON)
        raise ValueError("Event has no start")


class _ApiEvent(BaseModel):
    id: str
    summary: str = ""
    start: _When

    def to_event(self) -> Event:
        return Event(id=self.id, summary=self.summary, starts_at=self.start.to_datetime())


class _ApiEventPage(BaseModel):
    items: list[_ApiEvent] = []
    next_page_token: str | None = Field(default=None, alias="nextPageToken")


class GoogleCalendar:
    def __init__(self, calendar_id: str, service_account_info: dict[str, str]) -> None:
        credentials = Credentials.from_service_account_info(service_account_info, scopes=[SCOPE])
        self._session = AuthorizedSession(credentials)
        self._url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events"

    @classmethod
    def from_env(cls) -> "GoogleCalendar":
        return cls(os.environ["CALENDAR_ID"], json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]))

    def events_starting_after(self, moment: dt.datetime) -> list[Event]:
        events: list[Event] = []
        page_token: str | None = None
        while True:
            params = {"timeMin": moment.isoformat(), "singleEvents": "true", "maxResults": "2500"}
            if page_token:
                params["pageToken"] = page_token
            response = self._session.get(self._url, params=params, timeout=30)
            response.raise_for_status()
            page = _ApiEventPage.model_validate_json(response.content)
            events += [event.to_event() for event in page.items]
            if not (page_token := page.next_page_token):
                break
        # timeMin filters on end time, so events already in progress come back too.
        return [event for event in events if event.starts_at > moment]

    def delete(self, event: Event) -> None:
        self._session.delete(f"{self._url}/{event.id}", timeout=30).raise_for_status()

    def create(self, booking: Booking) -> Event:
        response = self._session.post(self._url, json=_body(booking), timeout=30)
        response.raise_for_status()
        return _ApiEvent.model_validate_json(response.content).to_event()


def _body(booking: Booking) -> dict[str, object]:
    if booking.slot is None:
        start: dict[str, str] = {"date": booking.day.isoformat()}
        end: dict[str, str] = {"date": (booking.day + dt.timedelta(days=1)).isoformat()}  # end date is exclusive
    else:
        start = {
            "dateTime": dt.datetime.combine(booking.day, booking.slot.start).isoformat(),
            "timeZone": "Europe/London",
        }
        end = {"dateTime": dt.datetime.combine(booking.day, booking.slot.end).isoformat(), "timeZone": "Europe/London"}
    sheet_url = f"{REPO}/tree/master/data/sheets/{booking.sheet_id}"
    description = (
        f"Time on the sheet: {booking.time_as_printed or '(blank)'}\n"
        f"Source sheet: {sheet_url}\n"
        f"Something wrong? {REPO}/issues/new"
    )
    return {
        "summary": booking.title,
        "location": "Battersea Park Millennium Arena",
        "description": description,
        "start": start,
        "end": end,
        "extendedProperties": {"private": {"sheet_id": booking.sheet_id}},
    }
