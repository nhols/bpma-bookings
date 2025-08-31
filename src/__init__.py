import logging
import os
from typing import TYPE_CHECKING

import boto3
from dotenv import load_dotenv

if TYPE_CHECKING:
    from types_boto3_ssm.client import SSMClient

logger = logging.getLogger(__name__)
PATH = "/bpma/"


def load_from_ssm():
    client: "SSMClient" = boto3.client("ssm")

    for parameter in client.get_parameters_by_path(Path=PATH, WithDecryption=True, Recursive=True)["Parameters"]:
        if not (param := parameter.get("Name")) or not (value := parameter.get("Value")):
            continue
        env_var_name = param.replace(PATH, "")
        os.environ[env_var_name] = value
    return True


logging.basicConfig(level=logging.INFO)
if not load_dotenv():
    logger.info(".env file not found or empty, attempting to load from SSM")
    if not load_from_ssm():
        logger.warning("Failed to load environment variables from both .env file and SSM")
