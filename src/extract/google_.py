import logging
import mimetypes
from pathlib import Path
from typing import cast

import requests
from google import genai

from src.bookings import Bookings

logger = logging.getLogger(__name__)

PROMPT = """
Extract ALL the bookings of the athletics track from the image.
If the image does not contain information about athletics track bookings, return `{"bookings": []}`
Make sure to get the year right, it may appear at the top of the image.
ONLY EXTRACT ATHLETICS TRACK BOOKINGS, if the image relates to some other type of bookings, return `{"bookings": []}`
"""


client = genai.Client()


def get_media_from_path(path: Path) -> genai.types.Part:
    with path.open("rb") as f:
        image_bytes = f.read()
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


def get_media_from_url(url: str) -> genai.types.Part:
    response = requests.get(url)
    image_bytes = response.content

    mime_type = response.headers.get("content-type")
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(url)
        if not mime_type:
            mime_type = "image/jpeg"

    return genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


def extract_bookings(part: genai.types.Part) -> Bookings | None:
    cfg = genai.types.GenerateContentConfigDict(
        response_mime_type="application/json",
        response_schema=Bookings,
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[part, PROMPT],
        config=cfg,
    )
    return cast(Bookings | None, response.parsed)


def extract_bookings_from_path(path: Path) -> Bookings | None:
    logger.info(f"Extracting bookings from path: {path}")
    part = get_media_from_path(path)
    return extract_bookings(part)


def extract_bookings_from_url(url: str) -> Bookings | None:
    logger.info(f"Extracting bookings from url: {url}")
    part = get_media_from_url(url)
    return extract_bookings(part)
