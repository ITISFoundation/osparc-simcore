import logging
import urllib.parse
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from aws_library.s3.client import SimcoreS3API
from aws_library.s3.errors import s3_exception_handler
from aws_library.s3.models import S3MetaData
from boto3.s3.transfer import TransferConfig
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import AnyUrl, ByteSize, parse_obj_as

from .constants import EXPAND_DIR_MAX_ITEM_COUNT, MULTIPART_UPLOADS_MIN_TOTAL_SIZE
from .models import S3BucketName

_logger = logging.getLogger(__name__)


NextContinuationToken: TypeAlias = str


@dataclass(frozen=True)
class S3FolderMetaData:
    size: int


class StorageS3Client(SimcoreS3API):  # pylint: disable=too-many-public-methods
    @s3_exception_handler(_logger)
    async def delete_files_in_project_node(
        self,
        bucket: S3BucketName,
        project_id: ProjectID,
        node_id: NodeID | None = None,
    ) -> None:
        await self.delete_file_recursively(
            bucket=bucket,
            prefix=f"{project_id}/{node_id}/" if node_id else f"{project_id}/",
        )

    async def _list_all_objects(
        self, bucket: S3BucketName, *, prefix: str
    ) -> AsyncGenerator[S3MetaData, None]:
        async for s3_objects in self.list_files_paginated(bucket=bucket, prefix=prefix):
            for obj in s3_objects:
                yield obj

    @s3_exception_handler(_logger)
    async def get_directory_metadata(
        self, bucket: S3BucketName, *, prefix: str
    ) -> S3FolderMetaData:
        size = 0
        async for s3_object in self._list_all_objects(bucket, prefix=prefix):
            size += s3_object.size
        return S3FolderMetaData(size=size)

    @s3_exception_handler(_logger)
    async def copy_file(
        self,
        bucket: S3BucketName,
        src_file: SimcoreS3FileID,
        dst_file: SimcoreS3FileID,
        bytes_transfered_cb: Callable[[int], None] | None,
    ) -> None:
        """copy a file in S3 using aioboto3 transfer manager (e.g. works >5Gb and creates multiple threads)

        :type bucket: S3BucketName
        :type src_file: SimcoreS3FileID
        :type dst_file: SimcoreS3FileID
        """
        copy_options = {
            "CopySource": {"Bucket": bucket, "Key": src_file},
            "Bucket": bucket,
            "Key": dst_file,
            "Config": TransferConfig(max_concurrency=self.transfer_max_concurrency),
        }
        if bytes_transfered_cb:
            copy_options |= {"Callback": bytes_transfered_cb}
        await self.client.copy(**copy_options)

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
        found_items: list[S3MetaData] = []
        async for s3_objects in self.list_files_paginated(
            bucket=bucket, prefix=prefix, items_per_page=max_files_to_list
        ):
            found_items.extend(s3_objects)
            # NOTE: stop immediately after listing after `max_files_to_list`
            break

        return found_items

    @s3_exception_handler(_logger)
    async def upload_file(
        self,
        bucket: S3BucketName,
        file: Path,
        file_id: SimcoreS3FileID,
        bytes_transfered_cb: Callable[[int], None] | None,
    ) -> None:
        """upload a file using aioboto3 transfer manager (e.g. works >5Gb and create multiple threads)

        :type bucket: S3BucketName
        :type file: Path
        :type file_id: SimcoreS3FileID
        """
        upload_options = {
            "Bucket": bucket,
            "Key": file_id,
            "Config": TransferConfig(max_concurrency=self.transfer_max_concurrency),
        }
        if bytes_transfered_cb:
            upload_options |= {"Callback": bytes_transfered_cb}
        await self.client.upload_file(f"{file}", **upload_options)

    @staticmethod
    def compute_s3_url(bucket: S3BucketName, file_id: SimcoreS3FileID) -> AnyUrl:
        url: AnyUrl = parse_obj_as(
            AnyUrl, f"s3://{bucket}/{urllib.parse.quote(file_id)}"
        )
        return url

    @staticmethod
    def is_multipart(file_size: ByteSize) -> bool:
        return file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE
