import datetime
import json
import logging
import os
from typing import TYPE_CHECKING, cast

from google.oauth2 import service_account
from googleapiclient.discovery import build

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import CalendarResource, Event, EventDateTime

from src.bookings import Booking, Bookings

logger = logging.getLogger(__name__)
CALENDAR_ID = os.getenv("CALENDAR_ID")
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


def booking_to_event(booking: Booking) -> "Event":
    title = "BPMA Track booked"
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
    return {
        "summary": title,
        "location": "Battersea Park Millennium Arena",
        "description": booking.model_dump_json(indent=2),
        "start": cast("EventDateTime", start),
        "end": cast("EventDateTime", end),
    }


def push_bookings_to_calendar(bookings: Bookings, id_: str) -> None:
    if not CALENDAR_ID:
        raise ValueError("CALENDAR_ID environment variable is not set")
    service = get_client()
    metadata = {"private": {"booking_id": id_}}

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
        event = booking_to_event(booking)
        event["extendedProperties"] = metadata

        batch.add(service.events().insert(calendarId=CALENDAR_ID, body=event), callback=callback, request_id=str(i))

    logger.info(f"Executing batch request with {len(bookings.bookings)} events")
    batch.execute()


def delete_all_events():
    if not CALENDAR_ID:
        raise ValueError("CALENDAR_ID environment variable is not set")
    service = get_client()

    events = service.events().list(calendarId=CALENDAR_ID).execute()
    for event in events.get("items", []):
        if event_id := event.get("id"):
            logger.info(f"Deleting event: {event.get('summary', 'Unknown')}")
            service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
