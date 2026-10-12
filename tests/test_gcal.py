from conftest import row, sheet

from bpma.gcal import _body
from bpma.sheet import bookings


def test_events_link_straight_to_the_sheet_image() -> None:
    [booking] = bookings(sheet(row("2026-10-13", ("12:00", "18:30"))), "9e68c66a", "image.png")
    description = str(_body(booking)["description"])
    assert "https://raw.githubusercontent.com/nhols/bpma-bookings/master/data/sheets/9e68c66a/image.png" in description


def test_all_day_events_end_the_next_day() -> None:
    [booking] = bookings(sheet(row("2025-10-24", time="TBA")), "sheet1", "image.jpg")
    body = _body(booking)
    assert (body["start"], body["end"]) == ({"date": "2025-10-24"}, {"date": "2025-10-25"})
