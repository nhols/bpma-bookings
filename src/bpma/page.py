"""Find the booking sheet images on the BPMA web page."""

import re
from urllib.parse import unquote_plus

import httpx
from pydantic import BaseModel, ConfigDict

PAGE_URL = "https://www.enableleisure.co.uk/battersea-park-millennium-arena-gym"

# e.g. https://images.squarespace-cdn.com/content/v1/64e4.../9e68c66a-0a09-4ba7-a8f4-73400fc050d6/9+Athletics+Track+Bookings.jpg
# The UUID identifies one upload. The CDN serves the same upload as different bytes over time, so never hash the file.
IMAGE_URL = re.compile(
    r"https://images\.squarespace-cdn\.com/content/v1/[^/\"]+/(?P<asset_id>[0-9a-f-]{36})/(?P<filename>[^/?\"\s]+)"
)


class SheetRef(BaseModel):
    """A booking sheet image on the page."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    url: str
    filename: str


def find_sheets(html: str) -> list[SheetRef]:
    """Every booking sheet image in the page, once each, in page order."""
    found: dict[str, SheetRef] = {}
    for match in IMAGE_URL.finditer(html):
        filename = unquote_plus(match["filename"])
        name = filename.lower()
        if "track" in name and "booking" in name:
            found.setdefault(match["asset_id"], SheetRef(asset_id=match["asset_id"], url=match[0], filename=filename))
    return list(found.values())


def fetch(url: str) -> httpx.Response:
    response = httpx.get(url, follow_redirects=True, timeout=30, headers={"User-Agent": "bpma-bookings"})
    return response.raise_for_status()
