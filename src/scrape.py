import re
from typing import Callable, List, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup, Tag

URL = "https://bluebird-carrot-kkzr.squarespace.com/battersea-park-millennium-arena-gym"


def is_booking_url(url: str) -> bool:
    u = url.lower()
    return all(kw in u for kw in ("athletics", "track", "bookings"))


def is_classes_timetable_url(url: str) -> bool:
    u = url.lower()
    return ("timetable" in u) and any(ext in u for ext in (".jpg", ".jpeg", ".png", ".webp", ".pdf"))


# -------------------- Core helpers --------------------
def _pick_from_srcset(srcset: str) -> Optional[str]:
    try:
        candidates: List[tuple[float, str]] = []
        for part in srcset.split(","):
            toks = part.strip().split()
            if not toks:
                continue
            url = toks[0]
            size = 0.0
            if len(toks) > 1 and toks[1].endswith("w"):
                try:
                    size = float(toks[1][:-1])
                except Exception:
                    pass
            candidates.append((size, url))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[-1][1]
    except Exception:
        return None


def _extract_candidate_image_urls(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls: List[str] = []
    # <img>
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-image"):
            val = img.get(attr)
            if isinstance(val, str):
                urls.append(urljoin(base_url, val))
        srcset = img.get("srcset")
        if isinstance(srcset, str):
            chosen = _pick_from_srcset(srcset)
            if chosen:
                urls.append(urljoin(base_url, chosen))

    # <source srcset>
    for source in soup.find_all("source"):
        if not isinstance(source, Tag):
            continue
        srcset = source.get("srcset")
        if isinstance(srcset, str):
            chosen = _pick_from_srcset(srcset)
            if chosen:
                urls.append(urljoin(base_url, chosen))

    # <a href>
    for a in soup.find_all("a"):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if isinstance(href, str):
            urls.append(urljoin(base_url, href))

    # inline style background-image: url(...)
    style_re = re.compile(r"background-image\s*:\s*url\(([^)]+)\)")
    for el in soup.find_all(style=True):
        if not isinstance(el, Tag):
            continue
        style = el.get("style")
        if not isinstance(style, str):
            continue
        for m in style_re.finditer(style):
            raw = m.group(1).strip("\"' ")
            urls.append(urljoin(base_url, raw))
    return urls


def _filter_and_dedupe(urls: List[str], predicate: Callable[[str], bool]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for u in urls:
        if predicate(u) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _sort_by_format_width(urls: List[str]) -> List[str]:
    def width_key(u: str) -> int:
        m = re.search(r"[?&]format=(\d+)w\b", u)
        try:
            return int(m.group(1)) if m else 0
        except Exception:
            return 0

    return sorted(urls, key=width_key, reverse=True)


# -------------------- Public API --------------------
def get_img_urls(
    page_url: str,
    predicate: Optional[Callable[[str], bool]] = None,
    *,
    sort_highres: bool = False,
) -> List[str]:
    """Generic image scraper.

    - Fetches the page and enumerates likely image URLs (img, srcset, links, inline styles).
    - Filters using the supplied predicate (defaults to is_booking_url for backward compatibility).
    - Deduplicates while preserving order.
    """
    pred = predicate or is_booking_url
    resp = requests.get(page_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    raw = _extract_candidate_image_urls(soup, page_url)
    urls = _filter_and_dedupe(raw, pred)
    return _sort_by_format_width(urls) if sort_highres else urls


def get_track_img_urls(page_url: str) -> List[str]:
    return get_img_urls(page_url, is_booking_url)


def get_classes_img_urls(page_url: str) -> List[str]:
    return get_img_urls(page_url, is_classes_timetable_url, sort_highres=True)


if __name__ == "__main__":
    # Simple manual test: print both track and classes image URLs
    print("Track Booking Image URLs:")
    for url in get_track_img_urls(URL):
        print(url)

    print("\nClass Booking Image URLs:")
    for url in get_classes_img_urls(URL):
        print(url)
