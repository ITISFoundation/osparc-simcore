import asyncio
import contextlib
import logging
import urllib.parse
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from models_library.api_schemas_storage import ETag, S3BucketName, UploadedPart
from models_library.basic_types import SHA256Str
from pydantic import AnyUrl, ByteSize, parse_obj_as
from servicelib.logging_utils import log_catch, log_context
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client
from types_aiobotocore_s3.literals import BucketLocationConstraintType
from types_aiobotocore_s3.type_defs import ObjectIdentifierTypeDef

from .constants import MULTIPART_UPLOADS_MIN_TOTAL_SIZE
from .errors import S3KeyNotFoundError, s3_exception_handler
from .models import (
    MultiPartUploadLinks,
    S3DirectoryMetaData,
    S3MetaData,
    S3ObjectKey,
    UploadID,
)
from .utils import compute_num_file_chunks

_logger = logging.getLogger(__name__)

_S3_MAX_CONCURRENCY_DEFAULT: Final[int] = 10
_DEFAULT_AWS_REGION: Final[str] = "us-east-1"
_MAX_ITEMS_PER_PAGE: Final[int] = 500


# TODO: copy_folder method
# Pedro's PR: https://github.com/ITISFoundation/osparc-simcore/pull/5301
@dataclass(frozen=True)
class SimcoreS3API:
    _client: S3Client
    _session: aioboto3.Session
    _exit_stack: contextlib.AsyncExitStack = field(
        default_factory=contextlib.AsyncExitStack
    )
    transfer_max_concurrency: int = _S3_MAX_CONCURRENCY_DEFAULT

    @s3_exception_handler(_logger)
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
        await self._exit_stack.aclose()

    async def http_check_bucket_connected(self, *, bucket: S3BucketName) -> bool:
        return await self.bucket_exists(bucket=bucket)

    @s3_exception_handler(_logger)
    async def create_bucket(
        self, *, bucket: S3BucketName, region: BucketLocationConstraintType
    ) -> None:
        with log_context(
            _logger, logging.INFO, msg=f"Create bucket {bucket} in {region}"
        ):
            try:
                # NOTE: see https://github.com/boto/boto3/issues/125 why this is so... (sic)
                # setting it for the us-east-1 creates issue when creating buckets
                create_bucket_config: dict[str, Any] = {"Bucket": f"{bucket}"}
                if region != _DEFAULT_AWS_REGION:
                    create_bucket_config["CreateBucketConfiguration"] = {
                        "LocationConstraint": region
                    }

                await self._client.create_bucket(**create_bucket_config)

            except self._client.exceptions.BucketAlreadyOwnedByYou:
                _logger.info(
                    "Bucket %s already exists and is owned by us",
                    bucket,
                )

    @s3_exception_handler(_logger)
    async def bucket_exists(self, *, bucket: S3BucketName) -> bool:
        """
        :raises: S3BucketInvalidError if not existing, not enough rights
        :raises: S3AccessError for any other error
        """
        with log_catch(_logger, reraise=False), log_context(
            _logger, logging.DEBUG, msg=f"Head bucket: {bucket}"
        ):
            await self._client.head_bucket(Bucket=bucket)
            return True
        return False

    @s3_exception_handler(_logger)
    async def file_exists(
        self, *, bucket: S3BucketName, object_key: S3ObjectKey
    ) -> bool:
        # SEE https://www.peterbe.com/plog/fastest-way-to-find-out-if-a-file-exists-in-s3
        response = await self._client.list_objects_v2(Bucket=bucket, Prefix=object_key)
        return len(response.get("Contents", [])) > 0

    @s3_exception_handler(_logger)
    async def get_file_metadata(
        self, *, bucket: S3BucketName, object_key: S3ObjectKey
    ) -> S3MetaData:
        response = await self._client.head_object(
            Bucket=bucket, Key=object_key, ChecksumMode="ENABLED"
        )
        return S3MetaData.from_botocore_head_object(object_key, response)

    @s3_exception_handler(_logger)
    async def get_directory_metadata(
        self, *, bucket: S3BucketName, prefix: str
    ) -> S3DirectoryMetaData:
        size = 0
        async for s3_object in self._list_all_objects(bucket=bucket, prefix=prefix):
            size += s3_object.size
        return S3DirectoryMetaData(size=size)

    # @s3_exception_handler(_logger)
    async def list_files_paginated(
        self,
        bucket: S3BucketName,
        prefix: str,
        *,
        items_per_page: int = _MAX_ITEMS_PER_PAGE,
    ) -> AsyncGenerator[list[S3MetaData], None]:

        async for page in self._client.get_paginator("list_objects_v2").paginate(
            Bucket=bucket,
            Prefix=prefix,
            PaginationConfig={
                "PageSize": items_per_page,
            },
        ):
            yield [
                S3MetaData.from_botocore_list_objects(obj)
                for obj in page.get("Contents", [])
            ]

    async def _list_all_objects(
        self, *, bucket: S3BucketName, prefix: str
    ) -> AsyncGenerator[S3MetaData, None]:
        async for s3_objects in self.list_files_paginated(bucket=bucket, prefix=prefix):
            for obj in s3_objects:
                yield obj

    @s3_exception_handler(_logger)
    async def delete_file_recursively(
        self, *, bucket: S3BucketName, prefix: str
    ) -> None:
        # NOTE: deletion of objects is done in batches of max 1000 elements,
        # the maximum accepted by the S3 API
        with log_context(
            _logger, logging.DEBUG, f"deleting objects in {prefix=}", log_duration=True
        ):
            async for s3_objects in self.list_files_paginated(
                bucket=bucket, prefix=prefix
            ):

                objects_to_delete: list[ObjectIdentifierTypeDef] = [
                    {"Key": _.object_key} for _ in s3_objects
                ]
                await self._client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": objects_to_delete},
                )

    @s3_exception_handler(_logger)
    async def delete_file(
        self, *, bucket: S3BucketName, object_key: S3ObjectKey
    ) -> None:
        await self._client.delete_object(Bucket=bucket, Key=object_key)

    @s3_exception_handler(_logger)
    async def undelete_file(
        self, *, bucket: S3BucketName, object_key: S3ObjectKey
    ) -> None:
        with log_context(
            _logger, logging.DEBUG, msg=f"undeleting {bucket}/{object_key}"
        ):
            response = await self._client.list_object_versions(
                Bucket=bucket, Prefix=object_key, MaxKeys=1
            )
            _logger.debug("%s", f"{response=}")

            if all(k not in response for k in ["Versions", "DeleteMarkers"]):
                # that means there is no such file_id
                raise S3KeyNotFoundError(key=object_key, bucket=bucket)

            if "DeleteMarkers" in response:
                latest_version = response["DeleteMarkers"][0]
                assert "IsLatest" in latest_version  # nosec
                assert "VersionId" in latest_version  # nosec
                if latest_version["IsLatest"]:
                    await self._client.delete_object(
                        Bucket=bucket,
                        Key=object_key,
                        VersionId=latest_version["VersionId"],
                    )
                    _logger.debug("restored %s", f"{bucket}/{object_key}")

    @s3_exception_handler(_logger)
    async def create_single_presigned_download_link(
        self,
        *,
        bucket: S3BucketName,
        object_key: S3ObjectKey,
        expiration_secs: int,
    ) -> AnyUrl:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self._client.head_bucket(Bucket=bucket)
        await self._client.head_object(Bucket=bucket, Key=object_key)
        generated_link = await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expiration_secs,
        )
        url: AnyUrl = parse_obj_as(AnyUrl, generated_link)
        return url

    @s3_exception_handler(_logger)
    async def create_single_presigned_upload_link(
        self, *, bucket: S3BucketName, object_key: S3ObjectKey, expiration_secs: int
    ) -> AnyUrl:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self._client.head_bucket(Bucket=bucket)
        generated_link = await self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": object_key},
            ExpiresIn=expiration_secs,
        )
        url: AnyUrl = parse_obj_as(AnyUrl, generated_link)
        return url

    @s3_exception_handler(_logger)
    async def create_multipart_upload_links(
        self,
        *,
        bucket: S3BucketName,
        object_key: S3ObjectKey,
        file_size: ByteSize,
        expiration_secs: int,
        sha256_checksum: SHA256Str | None,
    ) -> MultiPartUploadLinks:
        # NOTE: ensure the bucket exists, this will raise if not
        await self._client.head_bucket(Bucket=bucket)
        # first initiate the multipart upload
        create_input: dict[str, Any] = {"Bucket": bucket, "Key": object_key}
        if sha256_checksum:
            create_input["Metadata"] = {"sha256_checksum": sha256_checksum}
        response = await self._client.create_multipart_upload(**create_input)
        upload_id = response["UploadId"]
        # compute the number of links, based on the announced file size
        num_upload_links, chunk_size = compute_num_file_chunks(file_size)
        # now create the links
        upload_links = parse_obj_as(
            list[AnyUrl],
            await asyncio.gather(
                *(
                    self._client.generate_presigned_url(
                        "upload_part",
                        Params={
                            "Bucket": bucket,
                            "Key": object_key,
                            "PartNumber": i + 1,
                            "UploadId": upload_id,
                        },
                        ExpiresIn=expiration_secs,
                    )
                    for i in range(num_upload_links)
                ),
            ),
        )
        return MultiPartUploadLinks(
            upload_id=upload_id, chunk_size=chunk_size, urls=upload_links
        )

    @s3_exception_handler(_logger)
    async def list_ongoing_multipart_uploads(
        self,
        *,
        bucket: S3BucketName,
    ) -> list[tuple[UploadID, S3ObjectKey]]:
        """Returns all the currently ongoing multipart uploads

        NOTE: minio does not implement the same behaviour as AWS here and will
        only return the uploads if a prefix or object name is given [minio issue](https://github.com/minio/minio/issues/7632).

        :return: list of AWS uploads see [boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.list_multipart_uploads)
        """
        response = await self._client.list_multipart_uploads(
            Bucket=bucket,
        )

        return [
            (
                upload.get("UploadId", "undefined-uploadid"),
                S3ObjectKey(upload.get("Key", "undefined-key")),
            )
            for upload in response.get("Uploads", [])
        ]

    @s3_exception_handler(_logger)
    async def abort_multipart_upload(
        self, *, bucket: S3BucketName, object_key: S3ObjectKey, upload_id: UploadID
    ) -> None:
        await self._client.abort_multipart_upload(
            Bucket=bucket, Key=object_key, UploadId=upload_id
        )

    @s3_exception_handler(_logger)
    async def complete_multipart_upload(
        self,
        *,
        bucket: S3BucketName,
        object_key: S3ObjectKey,
        upload_id: UploadID,
        uploaded_parts: list[UploadedPart],
    ) -> ETag:
        inputs: dict[str, Any] = {
            "Bucket": bucket,
            "Key": object_key,
            "UploadId": upload_id,
            "MultipartUpload": {
                "Parts": [
                    {"ETag": part.e_tag, "PartNumber": part.number}
                    for part in uploaded_parts
                ]
            },
        }
        response = await self._client.complete_multipart_upload(**inputs)
        return response["ETag"]

    @s3_exception_handler(_logger)
    async def upload_file(
        self,
        *,
        bucket: S3BucketName,
        file: Path,
        object_key: S3ObjectKey,
        bytes_transfered_cb: Callable[[int], None] | None,
    ) -> None:
        """upload a file using aioboto3 transfer manager (e.g. works >5Gb and create multiple threads)"""
        upload_options = {
            "Bucket": bucket,
            "Key": object_key,
            "Config": TransferConfig(max_concurrency=self.transfer_max_concurrency),
        }
        if bytes_transfered_cb:
            upload_options |= {"Callback": bytes_transfered_cb}
        await self._client.upload_file(f"{file}", **upload_options)

    @s3_exception_handler(_logger)
    async def copy_file(
        self,
        *,
        bucket: S3BucketName,
        src_object_key: S3ObjectKey,
        dst_object_key: S3ObjectKey,
        bytes_transfered_cb: Callable[[int], None] | None,
    ) -> None:
        """copy a file in S3 using aioboto3 transfer manager (e.g. works >5Gb and creates multiple threads)"""
        copy_options = {
            "CopySource": {"Bucket": bucket, "Key": src_object_key},
            "Bucket": bucket,
            "Key": dst_object_key,
            "Config": TransferConfig(max_concurrency=self.transfer_max_concurrency),
        }
        if bytes_transfered_cb:
            copy_options |= {"Callback": bytes_transfered_cb}
        await self._client.copy(**copy_options)

    @s3_exception_handler(_logger)
    async def copy_files_recursively(
        self,
        *,
        bucket: S3BucketName,
        src_prefix: str,
        dst_prefix: str,
        bytes_transfered_cb: Callable[[int], None] | None,
    ) -> None:
        """copy from 1 location in S3 to another recreating the same structure"""
        async for s3_object in self._list_all_objects(bucket=bucket, prefix=src_prefix):
            dst_object_key = s3_object.object_key.replace(src_prefix, dst_prefix)
            await self.copy_file(
                bucket=bucket,
                src_object_key=s3_object.object_key,
                dst_object_key=dst_object_key,
                bytes_transfered_cb=bytes_transfered_cb,
            )

    @staticmethod
    def is_multipart(file_size: ByteSize) -> bool:
        return file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE

    @staticmethod
    def compute_s3_url(*, bucket: S3BucketName, object_key: S3ObjectKey) -> AnyUrl:
        url: AnyUrl = parse_obj_as(
            AnyUrl, f"s3://{bucket}/{urllib.parse.quote(object_key)}"
        )
        return url
