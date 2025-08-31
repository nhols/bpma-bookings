import difflib
import json
import logging
import time
from typing import Any

from src.bookings import Booking, Bookings
from src.eval.data import test_set
from src.extract.google_ import extract_bookings_from_path

logger = logging.getLogger(__name__)

REPS_PER_CASE = 3


def log_diff(expected: Bookings, actual: Bookings) -> None:
    exp_json = expected.model_dump_json(indent=2)
    resp_json = actual.model_dump_json(indent=2)

    logger.warning("Diff:")
    diff = difflib.unified_diff(exp_json.splitlines(), resp_json.splitlines(), lineterm="")
    for line in diff:
        logger.warning(line)


def normalise_booking(booking: Booking) -> Booking:
    booking = booking.model_copy(deep=True)
    if booking.event_type:
        booking.event_type = booking.event_type.strip().lower()
    if booking.any_other_info:
        booking.any_other_info = booking.any_other_info.strip().lower()
    return booking


def score(resp: Bookings | None, expected: Bookings) -> float:
    if not resp:
        logger.warning("No response received")
        return 0.0

    resp = Bookings(bookings=[normalise_booking(b) for b in resp.bookings])
    expected = Bookings(bookings=[normalise_booking(b) for b in expected.bookings])

    if resp == expected:
        logger.info("Perfect match!")
        return 1.0

    log_diff(expected, resp)
    return sum(1 for b in resp.bookings if b in expected.bookings) / max(len(expected.bookings), 1)


def main():
    scores: list[float] = []
    responses: dict[str, dict[int, Any]] = {}
    for path, bookings in test_set:
        responses[path.stem] = {}
        for case in range(REPS_PER_CASE):
            logger.info(f"Testing {path} (case {case + 1})")
            resp = extract_bookings_from_path(path)
            responses[path.stem][case] = resp.model_dump(mode="json") if resp else None
            scores.append(score(resp, bookings))
            logger.info(f"Score for {path} (case {case + 1}): {scores[-1]}")
        time.sleep(60)

    avg_score = sum(scores) / len(scores) if scores else 0.0
    logger.info(f"Average score over {len(scores)} runs: {avg_score}")
    with open("responses.json", "w") as f:
        json.dump(responses, f, indent=2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
