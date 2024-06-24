import logging
import urllib.parse
from typing import TypeAlias

from aws_library.s3.client import SimcoreS3API
from aws_library.s3.errors import s3_exception_handler
from aws_library.s3.models import S3MetaData
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import AnyUrl, parse_obj_as

from .constants import EXPAND_DIR_MAX_ITEM_COUNT
from .models import S3BucketName

_logger = logging.getLogger(__name__)


NextContinuationToken: TypeAlias = str


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

    @staticmethod
    def compute_s3_url(bucket: S3BucketName, file_id: SimcoreS3FileID) -> AnyUrl:
        url: AnyUrl = parse_obj_as(
            AnyUrl, f"s3://{bucket}/{urllib.parse.quote(file_id)}"
        )
        return url
