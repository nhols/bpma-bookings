import hashlib
import logging
import mimetypes
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import boto3
import requests

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client

from src.extract.google_ import extract_bookings_from_url
from src.gcal import push_bookings_to_calendar
from src.increment import increment_bookings
from src.scrape import URL, get_img_urls

logger = logging.getLogger(__name__)
BUCKET = os.getenv("S3_BUCKET_NAME")
MAX_DAYS = 30 * 4  # ~ 4 months
PROCESSING_STATUS_TAG = "processing_status"


class ProcessingStatus(StrEnum):
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ContentStoreResult:
    id_: str
    key: str
    s3_url: str
    should_process: bool
    processing_status: ProcessingStatus | None


def get_bucket_name() -> str:
    if not BUCKET:
        raise ValueError("`S3_BUCKET_NAME` environment variable is not set")
    return BUCKET


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


def put_processing_status(client: "S3Client", key: str, status: ProcessingStatus) -> None:
    bucket = get_bucket_name()
    logger.info(f"Tagging s3://{bucket}/{key} with {PROCESSING_STATUS_TAG}={status.value}")
    client.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": [{"Key": PROCESSING_STATUS_TAG, "Value": status.value}]},
    )


def get_processing_status(client: "S3Client", key: str) -> ProcessingStatus | None:
    bucket = get_bucket_name()
    response = client.get_object_tagging(Bucket=bucket, Key=key)
    tags = {tag["Key"]: tag["Value"] for tag in response.get("TagSet", [])}
    status = tags.get(PROCESSING_STATUS_TAG)
    if status is None:
        return None
    return ProcessingStatus(status)


def get_content_store_s3(url: str) -> ContentStoreResult:
    bucket = get_bucket_name()

    client: "S3Client" = boto3.client("s3")
    content = requests.get(url).content
    id_ = hashlib.sha256(content).hexdigest()
    ext, content_type = get_ext_content_type(url)
    key = f"{id_}{ext}"

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            IfNoneMatch="*",
        )
        return ContentStoreResult(
            id_=id_,
            key=key,
            s3_url=f"https://{bucket}.s3.amazonaws.com/{key}",
            should_process=True,
            processing_status=None,
        )
    except client.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "PreconditionFailed":
            logger.info("Object already exists in s3")
            status = get_processing_status(client, key)
            logger.info("Object status: %s", status)
            return ContentStoreResult(
                id_=id_,
                key=key,
                s3_url=f"https://{bucket}.s3.amazonaws.com/{key}",
                should_process=status != ProcessingStatus.COMPLETED,
                processing_status=status,
            )
        raise


def run():
    logger.info("Starting run function")
    img_urls = get_img_urls(URL)
    logger.info(f"Retrieved {len(img_urls)} image URLs")
    if len(img_urls) != 1:
        raise ValueError(f"Expected 1 image URL, found {len(img_urls)}: {img_urls}")

    img_url = img_urls[0]
    logger.info(f"Found image URL: {img_url}")

    result = get_content_store_s3(img_url)
    if not result.should_process:
        logger.info(f"Content already processed with ID: {result.id_}; skipping")
        return

    logger.info(
        f"Processing content with ID: {result.id_} at URL: {result.s3_url}"
        f" (status={result.processing_status or 'unset'})"
    )
    try:
        bookings = extract_bookings_from_url(img_url)
        if bookings is None or len(bookings.bookings) == 0:
            raise ValueError(f"No bookings found for url {img_url}")

        if bookings.range > MAX_DAYS:
            raise ValueError(f"Bookings range too large: {bookings.range} days, max is {MAX_DAYS}")

        incremented = increment_bookings(bookings)
        push_bookings_to_calendar(incremented, result.id_, result.s3_url)
    except Exception:
        client: "S3Client" = boto3.client("s3")
        put_processing_status(client, result.key, ProcessingStatus.FAILED)
        raise

    client = boto3.client("s3")
    put_processing_status(client, result.key, ProcessingStatus.COMPLETED)


if __name__ == "__main__":
    run()
