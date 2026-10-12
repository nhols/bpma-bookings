import datetime as dt

from conftest import row, sheet

from bpma.sheet import bookings, problems


def test_a_good_reading_has_no_problems() -> None:
    assert problems(sheet(row("2026-10-13", ("12:00", "18:30")))) == []


def test_weekday_typos_on_the_sheet_are_fine() -> None:
    reading = row("2026-06-03", ("08:30", "16:30")).model_copy(update={"weekday_as_printed": "WEDNEDAY"})
    assert problems(sheet(reading)) == []


def test_a_date_on_the_wrong_weekday_is_a_problem() -> None:
    wrong_year = row("2025-10-13", ("12:00", "18:30")).model_copy(update={"weekday_as_printed": "TUESDAY"})
    [problem] = problems(sheet(wrong_year))
    assert "is a Monday" in problem


def test_slots_that_end_before_they_start_are_a_problem() -> None:
    [problem] = problems(sheet(row("2026-10-13", ("18:30", "12:00"))))
    assert "ends before it starts" in problem


def test_an_empty_sheet_is_a_problem() -> None:
    assert problems(sheet()) == ["No rows were read from the sheet."]


def test_a_date_range_becomes_one_booking_per_day() -> None:
    result = bookings(sheet(row("2026-05-05", ("08:30", "16:30"), last_day="2026-05-08")), "sheet1", "image.jpg")
    assert [b.day for b in result] == [dt.date(2026, 5, d) for d in (5, 6, 7, 8)]


def test_two_slots_in_one_row_become_two_bookings() -> None:
    result = bookings(sheet(row("2026-03-04", ("11:00", "13:30"), ("17:30", "20:30"))), "sheet1", "image.jpg")
    assert [(b.slot.start, b.slot.end) for b in result if b.slot] == [
        (dt.time(11, 0), dt.time(13, 30)),
        (dt.time(17, 30), dt.time(20, 30)),
    ]


def test_rows_without_times_become_all_day_bookings_titled_with_the_printed_time() -> None:
    tba, closed = bookings(
        sheet(
            row("2025-10-24", time="TBA", event="EXCLUSIVE USE  TRACK BOOKING"),
            row("2025-12-25", time="-", event="CLOSED"),
        ),
        "sheet1",
        "image.jpg",
    )
    assert (tba.slot, tba.title) == (None, "Exclusive use track booking (TBA)")
    assert (closed.slot, closed.title) == (None, "Closed")
    assert tba.starts_at == dt.datetime(2025, 10, 24, tzinfo=tba.starts_at.tzinfo)
