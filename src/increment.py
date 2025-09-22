import datetime
import logging
from typing import TYPE_CHECKING

from src.bookings import Bookings
from src.gcal import delete_events, list_events

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import Event

logger = logging.getLogger(__name__)


def increment_bookings(new_bookings: Bookings) -> Bookings:
    """
    A set of bookings is assumed to cover the full range of the dates covered by the bookings.

    Any existing bookings in that range which are not in the new set will be deleted.

    Bookings which are in the new set but not in the existing set will be returned.

    New bookings are matched to existing bookings by their `booking_id` property.

    Args:
        new_bookings (Bookings): New candidate bookings to add.

    Returns:
        Bookings: The subset of `new_bookings` which are not already in the calendar.
    """

    from_to = bookings_min_max_dates(new_bookings)
    if from_to is None:
        return Bookings(bookings=[])

    events = list_events(*from_to)

    new_booking_ids = {b.booking_id for b in new_bookings.bookings}
    extant_booking_ids = {id_ for event in events if (id_ := get_booking_id(event)) is not None}

    logger.info(f"Found {len(extant_booking_ids)} existing bookings in calendar, {len(new_booking_ids)} new bookings")
    logger.info(f"{len(new_booking_ids & extant_booking_ids)} bookings already exist in calendar")
    logger.info(f"{len(new_booking_ids - extant_booking_ids)} new bookings to add to calendar")
    logger.info(f"{len(extant_booking_ids - new_booking_ids)} existing bookings to delete from calendar")
    logger.info(f"Deleting bookings: {extant_booking_ids - new_booking_ids}")

    to_delete = {
        id_ for event in events if get_booking_id(event) not in new_booking_ids and (id_ := event.get("id")) is not None
    }
    delete_events(list(to_delete))

    return Bookings(bookings=[b for b in new_bookings.bookings if b.booking_id not in extant_booking_ids])


def get_booking_id(event: "Event") -> str | None:
    return event.get("extendedProperties", {}).get("private", {}).get("booking_id")


def bookings_min_max_dates(bookings: Bookings) -> tuple[datetime.date, datetime.date] | None:
    if not bookings.bookings:
        return None

    min_date = min(booking.date for booking in bookings.bookings)
    max_date = max(booking.date for booking in bookings.bookings)
    return min_date, max_date


def bookings_from_to(bookings: Bookings) -> tuple[datetime.date, datetime.date] | None:
    """
    Args:
        bookings (Bookings): The bookings to get the dates from.

    Returns:
        `tuple[datetime.date, datetime.date]`: The from and to dates, or `None` if there are no bookings.

    Example:
        If bookings contain dates 2023-01-15, 2023-01-20, 2023-02-10, the function returns (2023-01-01, 2023-03-01).
    """
    if not bookings.bookings:
        return None

    min_max_date = bookings_min_max_dates(bookings)
    if min_max_date is None:
        return None
    min_date, max_date = min_max_date
    from_date = min_date.replace(day=1)
    to_date = (max_date.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    logger.info(f"Bookings cover from {from_date} to {to_date}")
    return from_date, to_date
