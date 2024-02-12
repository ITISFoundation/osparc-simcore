import datetime
import json
import logging
import urllib.parse
from collections.abc import AsyncGenerator, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeAlias, cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from models_library.api_schemas_storage import UploadedPart
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import AnyUrl, ByteSize, NonNegativeInt, parse_obj_as
from servicelib.logging_utils import log_context
from servicelib.utils import logged_gather
from settings_library.s3 import S3Settings
from types_aiobotocore_s3 import S3Client
from types_aiobotocore_s3.type_defs import (
    ListObjectsV2OutputTypeDef,
    ObjectTypeDef,
    PaginatorConfigTypeDef,
)

from .constants import EXPAND_DIR_MAX_ITEM_COUNT, MULTIPART_UPLOADS_MIN_TOTAL_SIZE
from .exceptions import S3KeyNotFoundError
from .models import ETag, MultiPartUploadLinks, S3BucketName, UploadID
from .s3_utils import compute_num_file_chunks, s3_exception_handler

_logger = logging.getLogger(__name__)


_MAX_ITEMS_PER_PAGE: Final[NonNegativeInt] = 500


NextContinuationToken: TypeAlias = str


@dataclass(frozen=True)
class S3MetaData:
    file_id: SimcoreS3FileID
    last_modified: datetime.datetime
    e_tag: ETag
    sha256_checksum: SHA256Str | None
    size: int

    @staticmethod
    def from_botocore_object(obj: ObjectTypeDef) -> "S3MetaData":
        assert "Key" in obj  # nosec
        assert "LastModified" in obj  # nosec
        assert "ETag" in obj  # nosec
        assert "Size" in obj  # nosec
        return S3MetaData(
            file_id=SimcoreS3FileID(obj["Key"]),
            last_modified=obj["LastModified"],
            e_tag=json.loads(obj["ETag"]),
            sha256_checksum=SHA256Str(obj.get("ChecksumSHA256"))
            if obj.get("ChecksumSHA256")
            else None,
            size=obj["Size"],
        )


async def _list_objects_v2_paginated_gen(
    client: S3Client,
    bucket: S3BucketName,
    prefix: str,
    *,
    items_per_page: int = _MAX_ITEMS_PER_PAGE,
) -> AsyncGenerator[list[ObjectTypeDef], None]:
    paginator = client.get_paginator("list_objects_v2")
    pagination_config: PaginatorConfigTypeDef = {
        "PageSize": items_per_page,
    }

    page: ListObjectsV2OutputTypeDef
    async for page in paginator.paginate(
        Bucket=bucket, Prefix=prefix, PaginationConfig=pagination_config
    ):
        items_in_page: list[ObjectTypeDef] = page.get("Contents", [])
        yield items_in_page


@dataclass
class StorageS3Client:  # pylint: disable=too-many-public-methods
    _session: aioboto3.Session
    _client: S3Client
    transfer_max_concurrency: int

    @classmethod
    async def create(
        cls, exit_stack: AsyncExitStack, settings: S3Settings, s3_max_concurrency: int
    ) -> "StorageS3Client":
        # upon creation the client does not try to connect, one need to make an operation
        session = aioboto3.Session()
        # NOTE: session.client returns an aiobotocore client enhanced with aioboto3 fcts (e.g. download_file, upload_file, copy_file...)
        session_client = session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            aws_session_token=settings.S3_ACCESS_TOKEN,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        assert isinstance(session_client, ClientCreatorContext)  # nosec
        client = cast(S3Client, await exit_stack.enter_async_context(session_client))
        # NOTE: this triggers a botocore.exception.ClientError in case the connection is not made to the S3 backend
        await client.list_buckets()

        return cls(
            _session=session,
            _client=client,
            transfer_max_concurrency=s3_max_concurrency,
        )

    @s3_exception_handler(_logger)
    async def create_bucket(self, bucket: S3BucketName) -> None:
        _logger.debug("Creating bucket: %s", bucket)
        try:
            await self._client.create_bucket(Bucket=bucket)
            _logger.info("Bucket %s successfully created", bucket)
        except self._client.exceptions.BucketAlreadyOwnedByYou:
            _logger.info(
                "Bucket %s already exists and is owned by us",
                bucket,
            )

    @s3_exception_handler(_logger)
    async def check_bucket_connection(self, bucket: S3BucketName) -> None:
        """
        :raises: S3BucketInvalidError if not existing, not enough rights
        :raises: S3AccessError for any other error
        """
        _logger.debug("Head bucket: %s", bucket)
        await self._client.head_bucket(Bucket=bucket)

    @s3_exception_handler(_logger)
    async def create_single_presigned_download_link(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID, expiration_secs: int
    ) -> AnyUrl:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self._client.head_bucket(Bucket=bucket)
        await self.get_file_metadata(bucket, file_id)
        generated_link = await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": file_id},
            ExpiresIn=expiration_secs,
        )
        url: AnyUrl = parse_obj_as(AnyUrl, generated_link)
        return url

    @s3_exception_handler(_logger)
    async def create_single_presigned_upload_link(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID, expiration_secs: int
    ) -> AnyUrl:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self._client.head_bucket(Bucket=bucket)
        generated_link = await self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": file_id},
            ExpiresIn=expiration_secs,
        )
        url: AnyUrl = parse_obj_as(AnyUrl, generated_link)
        return url

    @s3_exception_handler(_logger)
    async def create_multipart_upload_links(
        self,
        bucket: S3BucketName,
        file_id: SimcoreS3FileID,
        file_size: ByteSize,
        expiration_secs: int,
        sha256_checksum: SHA256Str | None,
    ) -> MultiPartUploadLinks:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self._client.head_bucket(Bucket=bucket)
        # first initiate the multipart upload
        create_input: dict[str, Any] = {"Bucket": bucket, "Key": file_id}
        if sha256_checksum:
            create_input["Metadata"] = {"sha256_checksum": sha256_checksum}
        response = await self._client.create_multipart_upload(**create_input)
        upload_id = response["UploadId"]
        # compute the number of links, based on the announced file size
        num_upload_links, chunk_size = compute_num_file_chunks(file_size)
        # now create the links
        upload_links = parse_obj_as(
            list[AnyUrl],
            await logged_gather(
                *[
                    self._client.generate_presigned_url(
                        "upload_part",
                        Params={
                            "Bucket": bucket,
                            "Key": file_id,
                            "PartNumber": i + 1,
                            "UploadId": upload_id,
                        },
                        ExpiresIn=expiration_secs,
                    )
                    for i in range(num_upload_links)
                ],
                log=_logger,
                max_concurrency=20,
            ),
        )
        return MultiPartUploadLinks(
            upload_id=upload_id, chunk_size=chunk_size, urls=upload_links
        )

    @s3_exception_handler(_logger)
    async def list_ongoing_multipart_uploads(
        self,
        bucket: S3BucketName,
    ) -> list[tuple[UploadID, SimcoreS3FileID]]:
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
                SimcoreS3FileID(upload.get("Key", "undefined-key")),
            )
            for upload in response.get("Uploads", [])
        ]

    @s3_exception_handler(_logger)
    async def abort_multipart_upload(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID, upload_id: UploadID
    ) -> None:
        await self._client.abort_multipart_upload(
            Bucket=bucket, Key=file_id, UploadId=upload_id
        )

    @s3_exception_handler(_logger)
    async def complete_multipart_upload(
        self,
        bucket: S3BucketName,
        file_id: SimcoreS3FileID,
        upload_id: UploadID,
        uploaded_parts: list[UploadedPart],
    ) -> ETag:
        inputs: dict[str, Any] = {
            "Bucket": bucket,
            "Key": file_id,
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
    async def delete_file(self, bucket: S3BucketName, file_id: SimcoreS3FileID) -> None:
        await self._client.delete_object(Bucket=bucket, Key=file_id)

    @s3_exception_handler(_logger)
    async def undelete_file(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID
    ) -> None:
        with log_context(_logger, logging.DEBUG, msg=f"undeleting {bucket}/{file_id}"):
            response = await self._client.list_object_versions(
                Bucket=bucket, Prefix=file_id, MaxKeys=1
            )
            _logger.debug("%s", f"{response=}")

            if all(k not in response for k in ["Versions", "DeleteMarkers"]):
                # that means there is no such file_id
                raise S3KeyNotFoundError(key=file_id, bucket=bucket)

            if "DeleteMarkers" in response:
                latest_version = response["DeleteMarkers"][0]
                assert "IsLatest" in latest_version  # nosec
                assert "VersionId" in latest_version  # nosec
                if latest_version["IsLatest"]:
                    await self._client.delete_object(
                        Bucket=bucket,
                        Key=file_id,
                        VersionId=latest_version["VersionId"],
                    )
                    _logger.debug("restored %s", f"{bucket}/{file_id}")

    async def iter_pages(
        self, bucket: S3BucketName, *, prefix: str
    ) -> AsyncGenerator[list[ObjectTypeDef], None]:
        async for s3_objects in _list_objects_v2_paginated_gen(
            self._client, bucket=bucket, prefix=prefix
        ):
            yield s3_objects

    @s3_exception_handler(_logger)
    async def delete_files_in_path(self, bucket: S3BucketName, *, prefix: str) -> None:
        """Removes one or more files from a given S3 path.

        # NOTE: the / at the end of the Prefix is VERY important,
        # makes the listing several order of magnitudes faster
        """

        # NOTE: deletion of objects is done in batches of max 1000 elements,
        # the maximum accepted by the S3 API
        with log_context(
            _logger, logging.INFO, f"deleting objects in {prefix=}", log_duration=True
        ):
            async for s3_objects in self.iter_pages(bucket, prefix=prefix):
                if objects_to_delete := [f["Key"] for f in s3_objects if "Key" in f]:
                    await self._client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": [{"Key": key} for key in objects_to_delete]},
                    )

    @s3_exception_handler(_logger)
    async def delete_files_in_project_node(
        self,
        bucket: S3BucketName,
        project_id: ProjectID,
        node_id: NodeID | None = None,
    ) -> None:
        await self.delete_files_in_path(
            bucket, prefix=f"{project_id}/{node_id}/" if node_id else f"{project_id}/"
        )

    @s3_exception_handler(_logger)
    async def get_file_metadata(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID
    ) -> S3MetaData:
        response = await self._client.head_object(
            Bucket=bucket, Key=file_id, ChecksumMode="ENABLED"
        )
        return S3MetaData(
            file_id=file_id,
            last_modified=response["LastModified"],
            e_tag=json.loads(response["ETag"]),
            sha256_checksum=response.get("ChecksumSHA256"),
            size=response["ContentLength"],
        )

    @s3_exception_handler(_logger)
    async def copy_file(
        self,
        bucket: S3BucketName,
        src_file: SimcoreS3FileID,
        dst_file: SimcoreS3FileID,
        bytes_transfered_cb: Callable[[int], None] | None,
    ) -> None:
        """Copies a file in S3 using aioboto3 transfer manager (e.g. works >5Gb and creates multiple threads)"""
        copy_options = {
            "CopySource": {"Bucket": bucket, "Key": src_file},
            "Bucket": bucket,
            "Key": dst_file,
            "Config": TransferConfig(max_concurrency=self.transfer_max_concurrency),
        }
        if bytes_transfered_cb:
            copy_options |= {"Callback": bytes_transfered_cb}
        await self._client.copy(**copy_options)

    @s3_exception_handler(_logger)
    async def list_files(
        self,
        bucket: S3BucketName,
        *,
        prefix: str,
        max_files_to_list: int = EXPAND_DIR_MAX_ITEM_COUNT,
    ) -> list[S3MetaData]:
        """
        NOTE: adding a / at the end of a folder improves speed by several orders of magnitudes
        This endpoint is currently limited to only return EXPAND_DIR_MAX_ITEM_COUNT by default
        """
        found_items: list[ObjectTypeDef] = []
        async for s3_objects in _list_objects_v2_paginated_gen(
            self._client, bucket, prefix, items_per_page=max_files_to_list
        ):
            found_items.extend(s3_objects)
            # NOTE: stop immediately after listing after `max_files_to_list`
            break

        return [
            S3MetaData.from_botocore_object(entry)
            for entry in found_items
            if all(k in entry for k in ("Key", "LastModified", "ETag", "Size"))
        ]

    @s3_exception_handler(_logger)
    async def file_exists(self, bucket: S3BucketName, *, s3_object: str) -> bool:
        """Checks if an S3 object exists"""
        # SEE https://www.peterbe.com/plog/fastest-way-to-find-out-if-a-file-exists-in-s3
        response = await self._client.list_objects_v2(Bucket=bucket, Prefix=s3_object)
        return len(response.get("Contents", [])) > 0

    @s3_exception_handler(_logger)
    async def upload_file(
        self,
        bucket: S3BucketName,
        file: Path,
        file_id: SimcoreS3FileID,
        bytes_transfered_cb: Callable[[int], None] | None,
    ) -> None:
        """Uploads a file using aioboto3 transfer manager (e.g. works >5Gb and create multiple threads)"""
        upload_options = {
            "Bucket": bucket,
            "Key": file_id,
            "Config": TransferConfig(max_concurrency=self.transfer_max_concurrency),
        }
        if bytes_transfered_cb:
            upload_options |= {"Callback": bytes_transfered_cb}
        await self._client.upload_file(f"{file}", **upload_options)

    @staticmethod
    def compute_s3_url(bucket: S3BucketName, file_id: SimcoreS3FileID) -> AnyUrl:
        url: AnyUrl = parse_obj_as(
            AnyUrl, f"s3://{bucket}/{urllib.parse.quote(file_id)}"
        )
        return url

    @staticmethod
    def is_multipart(file_size: ByteSize) -> bool:
        return file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE
