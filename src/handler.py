import logging

from src.run import run

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", force=True)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)


logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    logger.info(f"Lambda handler started. Event: {event}")
    logger.info(
        f"Context: request_id={context.aws_request_id}, remaining_time={context.get_remaining_time_in_millis()}"
    )

    try:
        run()
        logger.info("Lambda function completed successfully")
    except Exception:
        logger.exception("Error processing bookings")
        raise
