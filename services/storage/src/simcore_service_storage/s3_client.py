import logging
import urllib.parse
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeAlias

from aws_library.s3.client import SimcoreS3API
from aws_library.s3.errors import s3_exception_handler
from aws_library.s3.models import S3MetaData
from boto3.s3.transfer import TransferConfig
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import AnyUrl, ByteSize, NonNegativeInt, parse_obj_as
from servicelib.logging_utils import log_context
from types_aiobotocore_s3 import S3Client
from types_aiobotocore_s3.type_defs import (
    ListObjectsV2OutputTypeDef,
    ObjectTypeDef,
    PaginatorConfigTypeDef,
)

from .constants import EXPAND_DIR_MAX_ITEM_COUNT, MULTIPART_UPLOADS_MIN_TOTAL_SIZE
from .models import S3BucketName

_logger = logging.getLogger(__name__)


_MAX_ITEMS_PER_PAGE: Final[NonNegativeInt] = 500


NextContinuationToken: TypeAlias = str


@dataclass(frozen=True)
class S3FolderMetaData:
    size: int


async def _list_objects_v2_paginated_gen(
    client: S3Client,
    bucket: S3BucketName,
    prefix: str,
    *,
    items_per_page: int = _MAX_ITEMS_PER_PAGE,
) -> AsyncGenerator[list[ObjectTypeDef], None]:
    pagination_config: PaginatorConfigTypeDef = {
        "PageSize": items_per_page,
    }

    page: ListObjectsV2OutputTypeDef
    async for page in client.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix, PaginationConfig=pagination_config
    ):
        items_in_page: list[ObjectTypeDef] = page.get("Contents", [])
        yield items_in_page


class StorageS3Client(SimcoreS3API):  # pylint: disable=too-many-public-methods
    async def list_all_objects_gen(
        self, bucket: S3BucketName, *, prefix: str
    ) -> AsyncGenerator[list[ObjectTypeDef], None]:
        async for s3_objects in _list_objects_v2_paginated_gen(
            self.client, bucket=bucket, prefix=prefix
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
            async for s3_objects in self.list_all_objects_gen(bucket, prefix=prefix):
                if objects_to_delete := [f["Key"] for f in s3_objects if "Key" in f]:
                    await self.client.delete_objects(
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

    async def _list_all_objects(
        self, bucket: S3BucketName, *, prefix: str
    ) -> AsyncGenerator[ObjectTypeDef, None]:
        async for s3_objects in self.list_all_objects_gen(bucket, prefix=prefix):
            for obj in s3_objects:
                yield obj

    @s3_exception_handler(_logger)
    async def get_directory_metadata(
        self, bucket: S3BucketName, *, prefix: str
    ) -> S3FolderMetaData:
        size = 0
        async for s3_object in self._list_all_objects(bucket, prefix=prefix):
            assert "Size" in s3_object  # nosec
            size += s3_object["Size"]
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
        found_items: list[ObjectTypeDef] = []
        async for s3_objects in _list_objects_v2_paginated_gen(
            self.client, bucket, prefix, items_per_page=max_files_to_list
        ):
            found_items.extend(s3_objects)
            # NOTE: stop immediately after listing after `max_files_to_list`
            break

        return [
            S3MetaData.from_botocore_list_objects(entry)
            for entry in found_items
            if all(k in entry for k in ("Key", "LastModified", "ETag", "Size"))
        ]

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
