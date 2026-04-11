import datetime
import hashlib
import unittest
from unittest.mock import Mock, patch

from src.bookings import Booking, Bookings
from src.run import ContentStoreResult, ProcessingStatus, get_content_store_s3, run


class FakeS3Client:
    class exceptions:
        class ClientError(Exception):
            def __init__(self, error_code: str):
                self.response = {"Error": {"Code": error_code}}

    def __init__(self, should_exist: bool = False, tag_set: list[dict[str, str]] | None = None):
        self.should_exist = should_exist
        self.tag_set = tag_set or []
        self.put_calls = []
        self.put_tagging_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        if self.should_exist:
            raise self.exceptions.ClientError("PreconditionFailed")

    def get_object_tagging(self, **kwargs):
        return {"TagSet": self.tag_set}

    def put_object_tagging(self, **kwargs):
        self.put_tagging_calls.append(kwargs)
        self.tag_set = kwargs["Tagging"]["TagSet"]


def sample_bookings() -> Bookings:
    return Bookings(
        bookings=[
            Booking(
                date=datetime.date(2026, 4, 9),
                time="ALL DAY",
                event_type="Athletics Track",
            )
        ]
    )


class RunTests(unittest.TestCase):
    @patch("src.run.requests.get")
    @patch("src.run.boto3.client")
    def test_get_content_store_s3_skips_completed_content(self, mock_boto_client: Mock, mock_get: Mock):
        content = b"image-bytes"
        expected_id = hashlib.sha256(content).hexdigest()
        fake_client = FakeS3Client(
            should_exist=True,
            tag_set=[{"Key": "processing_status", "Value": "completed"}],
        )
        mock_boto_client.return_value = fake_client
        mock_get.return_value.content = content

        with patch("src.run.BUCKET", "test-bucket"):
            result = get_content_store_s3("https://example.com/image.png")

        self.assertEqual(
            result,
            ContentStoreResult(
                id_=expected_id,
                s3_url=f"https://test-bucket.s3.amazonaws.com/{expected_id}.png",
                should_process=False,
                processing_status=ProcessingStatus.COMPLETED,
            ),
        )
        self.assertEqual(fake_client.put_tagging_calls, [])

    @patch("src.run.requests.get")
    @patch("src.run.boto3.client")
    def test_get_content_store_s3_retries_when_existing_object_is_untagged(
        self, mock_boto_client: Mock, mock_get: Mock
    ):
        content = b"image-bytes"
        fake_client = FakeS3Client(should_exist=True)
        mock_boto_client.return_value = fake_client
        mock_get.return_value.content = content

        with patch("src.run.BUCKET", "test-bucket"):
            result = get_content_store_s3("https://example.com/image.png")

        self.assertTrue(result.should_process)
        self.assertIsNone(result.processing_status)
        self.assertEqual(fake_client.put_tagging_calls, [])

    @patch("src.run.requests.get")
    @patch("src.run.boto3.client")
    def test_get_content_store_s3_retries_when_existing_object_is_failed(self, mock_boto_client: Mock, mock_get: Mock):
        content = b"image-bytes"
        expected_id = hashlib.sha256(content).hexdigest()
        fake_client = FakeS3Client(
            should_exist=True,
            tag_set=[{"Key": "processing_status", "Value": "failed"}],
        )
        mock_boto_client.return_value = fake_client
        mock_get.return_value.content = content

        with patch("src.run.BUCKET", "test-bucket"):
            result = get_content_store_s3("https://example.com/image.png")

        self.assertEqual(
            result,
            ContentStoreResult(
                id_=expected_id,
                s3_url=f"https://test-bucket.s3.amazonaws.com/{expected_id}.png",
                should_process=True,
                processing_status=ProcessingStatus.FAILED,
            ),
        )
        self.assertEqual(fake_client.put_tagging_calls, [])

    @patch("src.run.boto3.client")
    @patch("src.run.push_bookings_to_calendar")
    @patch("src.run.increment_bookings")
    @patch("src.run.extract_bookings_from_url")
    @patch("src.run.get_content_store_s3")
    @patch("src.run.get_img_urls")
    def test_run_marks_completed_after_success(
        self,
        mock_get_img_urls: Mock,
        mock_get_content_store_s3: Mock,
        mock_extract_bookings_from_url: Mock,
        mock_increment_bookings: Mock,
        mock_push_bookings_to_calendar: Mock,
        mock_boto_client: Mock,
    ):
        bookings = sample_bookings()
        fake_client = FakeS3Client()
        mock_boto_client.return_value = fake_client
        mock_get_img_urls.return_value = ["https://example.com/image.png"]
        mock_get_content_store_s3.return_value = ContentStoreResult(
            id_="source-id",
            s3_url="https://bucket.s3.amazonaws.com/source-id.png",
            should_process=True,
            processing_status=None,
        )
        mock_extract_bookings_from_url.return_value = bookings
        mock_increment_bookings.return_value = bookings

        run()

        mock_push_bookings_to_calendar.assert_called_once_with(
            bookings,
            "source-id",
            "https://bucket.s3.amazonaws.com/source-id.png",
        )
        self.assertEqual(
            fake_client.put_tagging_calls[-1]["Tagging"]["TagSet"],
            [{"Key": "processing_status", "Value": "completed"}],
        )

    @patch("src.run.boto3.client")
    @patch("src.run.extract_bookings_from_url")
    @patch("src.run.get_content_store_s3")
    @patch("src.run.get_img_urls")
    def test_run_marks_failed_when_processing_raises(
        self,
        mock_get_img_urls: Mock,
        mock_get_content_store_s3: Mock,
        mock_extract_bookings_from_url: Mock,
        mock_boto_client: Mock,
    ):
        fake_client = FakeS3Client()
        mock_boto_client.return_value = fake_client
        mock_get_img_urls.return_value = ["https://example.com/image.png"]
        mock_get_content_store_s3.return_value = ContentStoreResult(
            id_="source-id",
            s3_url="https://bucket.s3.amazonaws.com/source-id.png",
            should_process=True,
            processing_status=ProcessingStatus.FAILED,
        )
        mock_extract_bookings_from_url.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            run()

        self.assertEqual(
            fake_client.put_tagging_calls[-1]["Tagging"]["TagSet"],
            [{"Key": "processing_status", "Value": "failed"}],
        )

    @patch("src.run.boto3.client")
    @patch("src.run.push_bookings_to_calendar")
    @patch("src.run.increment_bookings")
    @patch("src.run.extract_bookings_from_url")
    @patch("src.run.get_content_store_s3")
    @patch("src.run.get_img_urls")
    def test_run_skips_completed_content(
        self,
        mock_get_img_urls: Mock,
        mock_get_content_store_s3: Mock,
        mock_extract_bookings_from_url: Mock,
        mock_increment_bookings: Mock,
        mock_push_bookings_to_calendar: Mock,
        mock_boto_client: Mock,
    ):
        mock_boto_client.return_value = FakeS3Client()
        mock_get_img_urls.return_value = ["https://example.com/image.png"]
        mock_get_content_store_s3.return_value = ContentStoreResult(
            id_="source-id",
            s3_url="https://bucket.s3.amazonaws.com/source-id.png",
            should_process=False,
            processing_status=ProcessingStatus.COMPLETED,
        )

        run()

        mock_extract_bookings_from_url.assert_not_called()
        mock_increment_bookings.assert_not_called()
        mock_push_bookings_to_calendar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
