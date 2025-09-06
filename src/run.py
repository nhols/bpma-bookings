import hashlib
import logging
import mimetypes
import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import boto3
import requests

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client

from src.extract.google_ import extract_bookings_from_url
from src.gcal import push_bookings_to_calendar
from src.scrape import URL, get_track_img_urls

logger = logging.getLogger(__name__)
BUCKET = os.getenv("S3_BUCKET_NAME")


def get_ext_content_type(url: str) -> tuple[str, str]:
    parsed_url = urlparse(url)
    content_type, _ = mimetypes.guess_type(parsed_url.path)
    if not content_type:
        content_type = "image/jpeg"

    ext = mimetypes.guess_extension(content_type)
    if not ext:
        if content_type.startswith("image/"):
            ext = ".jpg"
        elif content_type == "application/pdf":
            ext = ".pdf"
        else:
            ext = ".bin"

    return ext, content_type


def get_content_store_s3(url: str) -> tuple[str, str] | None:
    if not BUCKET:
        raise ValueError("`S3_BUCKET_NAME` environment variable is not set")

    client: "S3Client" = boto3.client("s3")
    content = requests.get(url).content
    id_ = hashlib.sha256(content).hexdigest()
    ext, content_type = get_ext_content_type(url)
    key = f"{id_}{ext}"

    try:
        client.put_object(Bucket=BUCKET, Key=key, Body=content, ContentType=content_type, IfNoneMatch="*")
    except client.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "PreconditionFailed":
            logger.info("Object already exists in s3")
            return None
        raise

    # Construct the S3 object URL
    s3_url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
    return id_, s3_url


def run():
    logger.info("Starting run function")
    img_urls = get_track_img_urls(URL)
    logger.info(f"Retrieved {len(img_urls)} image URLs")
    if len(img_urls) != 1:
        raise ValueError(f"Expected 1 image URL, found {len(img_urls)}: {img_urls}")

    img_url = img_urls[0]
    logger.info(f"Found image URL: {img_url}")

    result = get_content_store_s3(img_url)
    if result is None:
        logger.info("No new image, skipping")
        return

    id_, s3_url = result
    logger.info(f"New content stored with ID: {id_} at URL: {s3_url}")
    bookings = extract_bookings_from_url(img_url)
    if bookings is None or len(bookings.bookings) == 0:
        raise ValueError(f"No bookings found for url {img_url}")

    # TODO update/delete existing events?
    push_bookings_to_calendar(bookings, id_, s3_url)


if __name__ == "__main__":
    run()
