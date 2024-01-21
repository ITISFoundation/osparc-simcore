import logging
from typing import cast

import boto3
from aws_library.s3.errors import S3NotConnectedError
from botocore.config import Config
from fastapi import FastAPI
from pydantic import AnyUrl, parse_obj_as
from settings_library.s3 import S3Settings

from ..core.errors import ConfigurationError

_logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self, access_key=None, secret_key=None, region=None):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.s3_client = self.create_s3_client()

    def create_s3_client(self):
        s3_client = boto3.client(
            "s3",
            config=Config(signature_version="s3v4"),
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        return s3_client

    def ping(self):
        try:
            self.s3_client.list_buckets()
            return True
        except Exception as e:
            print(f"Failed to ping S3: {str(e)}")
            return False

    def close(self):
        try:
            # Close the S3 client
            self.s3_client.meta.client.close()
            print("S3 client closed.")
        except Exception as e:
            print(f"Failed to close S3 client: {str(e)}")

    def generate_presigned_url(self, bucket, key, expiration=3600) -> AnyUrl:
        """
        Generate a pre-signed URL for the specified S3 object.

        :param bucket: The S3 bucket name.
        :param key: The key of the S3 object.
        :param expiration: The expiration time of the URL in seconds (default is 1 hour).
        :return: The pre-signed URL.
        """
        url = self.s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": "attachment",
            },
            ExpiresIn=expiration,
        )
        return cast(AnyUrl, parse_obj_as(AnyUrl, url))


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.s3_client = None
        settings: S3Settings | None = app.state.settings.RESOURCE_USAGE_TRACKER_S3

        if not settings:
            _logger.warning("S3 client is de-activated in the settings")
            return

        app.state.s3_client = client = S3Client(
            settings.S3_ACCESS_KEY, settings.S3_SECRET_KEY, settings.S3_REGION
        )

        if not client.ping():
            raise S3NotConnectedError  # pragma: no cover

    async def on_shutdown() -> None:
        if app.state.s3_client:
            cast(S3Client, app.state.s3_client).close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_s3_client(app: FastAPI) -> S3Client:
    if not app.state.s3_client:
        raise ConfigurationError(
            msg="S3 client is not available. Please check the configuration."
        )
    return cast(
        S3Client, app.state.s3_client
    )  # cast(SimcoreS3API, app.state.s3_client)
