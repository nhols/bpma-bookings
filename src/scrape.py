import re
from typing import List
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup, Tag

URL = "https://bluebird-carrot-kkzr.squarespace.com/battersea-park-millennium-arena-gym"


def is_track_booking_url(url: str) -> bool:
    return all(kw in url.lower() for kw in ["athletics", "track", "bookings"])


def is_class_timetable_url(url: str) -> bool:
    return all(kw in url.lower() for kw in ["fitness", "class", "timetable"])

def _extract_img_urls(page_url: str, predicate) -> list[str]:
    resp = requests.get(page_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    return [img["src"] for img in soup.select("img[src]") if predicate(img["src"])]

def get_class_img_url(page_url: str) -> list[str]:
    return _extract_img_urls(page_url, is_class_timetable_url)

def get_track_img_urls(page_url: str) -> list[str]:
    return _extract_img_urls(page_url, is_track_booking_url)

if __name__ == "__main__":
    print("Track Booking Image URLs:")
    for url in get_track_img_urls(URL):
        print(url)
    print("\nClass Booking Image URLs:")
    for url in get_class_img_url(URL):
        print(url)
