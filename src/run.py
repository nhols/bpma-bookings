import hashlib
import logging
import os
from typing import TYPE_CHECKING

import boto3
import requests

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client

from src.extract.google_ import extract_bookings_from_url
from src.gcal import push_bookings_to_calendar
from src.scrape import URL, get_img_urls

logger = logging.getLogger(__name__)
BUCKET = os.getenv("S3_BUCKET_NAME")


def get_content_store_s3(url: str) -> str | None:
    if not BUCKET:
        raise ValueError("`S3_BUCKET_NAME` environment variable is not set")

    client: "S3Client" = boto3.client("s3")
    content = requests.get(url).content
    id_ = hashlib.sha256(content).hexdigest()

    try:
        client.put_object(Bucket=BUCKET, Key=id_, Body=content, IfNoneMatch="*")
    except client.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "PreconditionFailed":
            logger.info("Object already exists in s3")
            return None
        raise
    return id_


def run():
    logger.info("Starting run function")
    img_urls = get_img_urls(URL)
    logger.info(f"Retrieved {len(img_urls)} image URLs")
    if len(img_urls) != 1:
        raise ValueError(f"Expected 1 image URL, found {len(img_urls)}: {img_urls}")

    img_url = img_urls[0]
    logger.info(f"Found image URL: {img_url}")

    id_ = get_content_store_s3(img_url)
    if id_ is None:
        logger.info("No new image, skipping")
        return

    logger.info(f"New content stored with ID: {id_}")
    bookings = extract_bookings_from_url(img_url)
    if bookings is None or len(bookings.bookings) == 0:
        raise ValueError(f"No bookings found for url {img_url}")

    # TODO update/delete existing events?
    push_bookings_to_calendar(bookings, id_)


if __name__ == "__main__":
    run()
