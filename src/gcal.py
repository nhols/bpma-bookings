import datetime
import json
import logging
import os
from typing import TYPE_CHECKING, cast

from google.oauth2 import service_account
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import CalendarResource, Event, EventDateTime

from src.bookings import Booking, Bookings

logger = logging.getLogger(__name__)
CALENDAR_ID = os.environ["CALENDAR_ID"]

TZ = "Europe/London"


def get_client() -> "CalendarResource":
    service_account_info = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_info:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set")

    try:
        service_account_data = json.loads(service_account_info)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON environment variable")

    creds = service_account.Credentials.from_service_account_info(
        service_account_data, scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=creds)
    return cast("CalendarResource", service)


def booking_to_html(booking: Booking, s3_url: str | None = None) -> str:
    """Convert a booking to HTML format for display."""
    html = "<div class='booking'>"
    html += "<h3>BPMA Track Booking</h3>"
    html += f"<p><strong>Date:</strong> {booking.date.strftime('%A, %B %d, %Y')}</p>"

    if isinstance(booking.time, str):
        html += f"<p><strong>Time:</strong> {booking.time}</p>"
    else:
        start_time = booking.time.start.strftime("%H:%M")
        end_time = booking.time.end.strftime("%H:%M")
        html += f"<p><strong>Time:</strong> {start_time} - {end_time}</p>"

    if booking.event_type:
        html += f"<p><strong>Event Type:</strong> {booking.event_type}</p>"
    if booking.any_other_info:
        html += f"<p><strong>Additional Info:</strong> {booking.any_other_info}</p>"
    if s3_url:
        html += f"<p><strong>Source Image:</strong> {s3_url}</p>"

    html += "</div>"
    return html


def booking_to_event(booking: Booking, s3_url: str | None = None, source_id: str | None = None) -> "Event":
    title = booking.event_type or "BPMA Track booked"
    if isinstance(booking.time, str):
        title += f" ({booking.time})"
        start = {
            "date": booking.date.isoformat(),
            "timeZone": TZ,
        }
        end = start
    else:
        start_dt = datetime.datetime.combine(booking.date, booking.time.start)
        end_dt = datetime.datetime.combine(booking.date, booking.time.end)
        start = {
            "dateTime": start_dt.isoformat(),
            "timeZone": TZ,
        }
        end = {
            "dateTime": end_dt.isoformat(),
            "timeZone": TZ,
        }
    private_props = {"booking_id": booking.booking_id}
    if source_id:
        private_props["source_id"] = source_id
    return {
        "summary": title,
        "location": "Battersea Park Millennium Arena",
        "description": booking_to_html(booking, s3_url),
        "start": cast("EventDateTime", start),
        "end": cast("EventDateTime", end),
        "extendedProperties": {"private": private_props},
    }


def push_bookings_to_calendar(bookings: Bookings, id_: str, s3_url: str | None = None) -> None:
    service = get_client()

    if not bookings.bookings:
        logger.info("No bookings to push to calendar")
        return

    def callback(request_id, response, exception):
        if exception is not None:
            logger.error(f"Error creating event for request {request_id}: {exception}")
        else:
            logger.info(f"Successfully created event: {response.get('summary', 'Unknown')}")

    batch = service.new_batch_http_request()
    for i, booking in enumerate(bookings.bookings):
        logger.info(f"Adding booking to batch: {booking}")
        event = booking_to_event(booking, s3_url, id_)
        batch.add(service.events().insert(calendarId=CALENDAR_ID, body=event), callback=callback, request_id=str(i))

    logger.info(f"Executing batch request with {len(bookings.bookings)} events")
    batch.execute()


def list_events(from_date: datetime.date, to_date: datetime.date) -> list["Event"]:
    service = get_client()

    tz = ZoneInfo(TZ)
    time_min = datetime.datetime.combine(from_date, datetime.time.min, tzinfo=tz).isoformat()
    time_max = datetime.datetime.combine(to_date, datetime.time.min, tzinfo=tz).isoformat()

    logger.info(f"Listing events from {time_min} to {time_max}")
    events_result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


def delete_events(event_ids: list[str]) -> None:
    service = get_client()

    def callback(request_id, response, exception):
        if exception is not None:
            logger.error(f"Error deleting event for request {request_id}: {exception}")
        else:
            logger.info(f"Successfully deleted event with ID: {request_id}")

    batch = service.new_batch_http_request()
    for event_id in event_ids:
        logger.info(f"Adding delete request to batch for event ID: {event_id}")
        batch.add(
            service.events().delete(calendarId=CALENDAR_ID, eventId=event_id), callback=callback, request_id=event_id
        )

    logger.info(f"Executing batch delete request with {len(event_ids)} events")
    batch.execute()


def delete_all_events():
    service = get_client()

    events = service.events().list(calendarId=CALENDAR_ID).execute()
    for event in events.get("items", []):
        if event_id := event.get("id"):
            logger.info(f"Deleting event: {event.get('summary', 'Unknown')}")
            service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
