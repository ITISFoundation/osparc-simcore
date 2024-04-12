import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from botocore.client import Config
from models_library.api_schemas_storage import S3BucketName
from pydantic import AnyUrl, parse_obj_as
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client

from .errors import s3_exception_handler

_logger = logging.getLogger(__name__)

_S3_MAX_CONCURRENCY_DEFAULT = 10


@dataclass(frozen=True)
class SimcoreS3API:
    client: S3Client
    session: aioboto3.Session
    exit_stack: contextlib.AsyncExitStack
    transfer_max_concurrency: int

    @classmethod
    async def create(
        cls, settings: S3Settings, s3_max_concurrency: int = _S3_MAX_CONCURRENCY_DEFAULT
    ) -> "SimcoreS3API":
        session = aioboto3.Session()
        session_client = session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        assert isinstance(session_client, ClientCreatorContext)  # nosec
        exit_stack = contextlib.AsyncExitStack()
        s3_client = cast(S3Client, await exit_stack.enter_async_context(session_client))
        # NOTE: this triggers a botocore.exception.ClientError in case the connection is not made to the S3 backend
        await s3_client.list_buckets()

        return cls(s3_client, session, exit_stack, s3_max_concurrency)

    async def close(self) -> None:
        await self.exit_stack.aclose()

    async def http_check_bucket_connected(self, bucket: S3BucketName) -> bool:
        try:
            _logger.debug("Head bucket: %s", bucket)
            await self.client.head_bucket(Bucket=bucket)
            return True
        except Exception:  # pylint: disable=broad-except
            return False

    @s3_exception_handler(_logger)
    async def create_single_presigned_download_link(
        self,
        bucket_name: S3BucketName,
        object_key: str,
        expiration_secs: int,
    ) -> AnyUrl:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self.client.head_bucket(Bucket=bucket_name)
        generated_link = await self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_key},
            ExpiresIn=expiration_secs,
        )
        url: AnyUrl = parse_obj_as(AnyUrl, generated_link)
        return url
