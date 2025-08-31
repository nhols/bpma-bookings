import requests
from bs4 import BeautifulSoup, Tag

URL = "https://bluebird-carrot-kkzr.squarespace.com/battersea-park-millennium-arena-gym"


def is_booking_url(url: str) -> bool:
    return all(kw in url.lower() for kw in ["athletics", "track", "bookings"])


def get_img_urls(page_url: str):
    resp = requests.get(page_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    img_tags = soup.find_all("img")
    urls = []
    for img_tag in img_tags:
        if isinstance(img_tag, Tag) and (url := img_tag.get("src")) and isinstance(url, str) and is_booking_url(url):
            urls.append(url)
    return urls


if __name__ == "__main__":
    img_urls = get_img_urls(URL)
    for url in img_urls:
        print(url)
