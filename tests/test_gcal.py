import datetime
import importlib
import os
import unittest
from unittest.mock import patch

from src.bookings import Booking


class GCalTests(unittest.TestCase):
    @patch.dict(os.environ, {"CALENDAR_ID": "test-calendar"}, clear=False)
    def test_booking_to_html_includes_prefilled_issue_link(self):
        gcal = importlib.import_module("src.gcal")
        booking = Booking(
            date=datetime.date(2026, 4, 9),
            time="ALL DAY",
            event_type="Athletics Track",
        )

        html = gcal.booking_to_html(
            booking,
            "https://bucket.s3.amazonaws.com/source-id.png",
            "source-id",
        )

        self.assertIn("Something looks off?", html)
        self.assertIn("Raise an issue here", html)
        self.assertIn("https://github.com/nhols/bpma-bookings/issues/new?", html)
        self.assertIn("title=Calendar+booking+issue", html)
        self.assertIn("Source+ID%3A+source-id", html)
        self.assertIn("Source+image%3A+https%3A%2F%2Fbucket.s3.amazonaws.com%2Fsource-id.png", html)


if __name__ == "__main__":
    unittest.main()
