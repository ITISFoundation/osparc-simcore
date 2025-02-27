from contextlib import suppress
from pathlib import Path

import orjson
from aws_library.s3 import S3MetaData, SimcoreS3API
from models_library.api_schemas_storage.storage_schemas import S3BucketName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import (
    SimcoreS3DirectoryID,
    SimcoreS3FileID,
    StorageFileID,
)
from pydantic import ByteSize, NonNegativeInt, TypeAdapter
from servicelib.utils import ensure_ends_with
from sqlalchemy.ext.asyncio import AsyncConnection

from ..exceptions.errors import FileMetaDataNotFoundError
from ..models import FileMetaData, FileMetaDataAtDB, GenericCursor, PathMetaData
from ..modules.db import file_meta_data
from .utils import convert_db_to_model


async def _list_all_files_in_folder(
    *,
    s3_client: SimcoreS3API,
    bucket: S3BucketName,
    prefix: str,
    max_files_to_list: int,
) -> list[S3MetaData]:
    async for s3_objects in s3_client.list_objects_paginated(
        bucket, prefix, items_per_page=max_files_to_list
    ):
        # NOTE: stop immediately after listing after `max_files_to_list`
        return s3_objects
    return []


async def expand_directory(
    s3_client: SimcoreS3API,
    simcore_bucket_name: S3BucketName,
    fmd: FileMetaDataAtDB,
    max_items_to_include: NonNegativeInt,
) -> list[FileMetaData]:
    """
    Scans S3 backend and returns a list S3MetaData entries which get mapped
    to FileMetaData entry.
    """
    files_in_folder: list[S3MetaData] = await _list_all_files_in_folder(
        s3_client=s3_client,
        bucket=simcore_bucket_name,
        prefix=ensure_ends_with(fmd.file_id, "/"),
        max_files_to_list=max_items_to_include,
    )
    result: list[FileMetaData] = [
        convert_db_to_model(
            FileMetaDataAtDB(
                location_id=fmd.location_id,
                location=fmd.location,
                bucket_name=fmd.bucket_name,
                object_name=x.object_key,
                user_id=fmd.user_id,
                # NOTE: to ensure users have a consistent experience the
                # `created_at` field is inherited from the last_modified
                # coming from S3. This way if a file is created 1 month after the
                # creation of the directory, the file's creation date
                # will not be 1 month in the passed.
                created_at=x.last_modified,
                file_id=x.object_key,
                file_size=TypeAdapter(ByteSize).validate_python(x.size),
                last_modified=x.last_modified,
                entity_tag=x.e_tag,
                is_soft_link=False,
                is_directory=False,
                project_id=fmd.project_id,
                node_id=fmd.node_id,
            )
        )
        for x in files_in_folder
    ]
    return result


def get_simcore_directory(file_id: SimcoreS3FileID) -> str:
    try:
        directory_id = SimcoreS3DirectoryID.from_simcore_s3_object(file_id)
    except ValueError:
        return ""
    return f"{Path(directory_id)}"


async def get_directory_file_id(
    conn: AsyncConnection, file_id: SimcoreS3FileID
) -> SimcoreS3FileID | None:
    """
    returns the containing file's `directory_file_id` if the entry exists
    in the `file_meta_data` table
    """

    async def _get_fmd(
        conn: AsyncConnection, s3_file_id: StorageFileID
    ) -> FileMetaDataAtDB | None:
        with suppress(FileMetaDataNotFoundError):
            return await file_meta_data.get(
                conn, TypeAdapter(SimcoreS3FileID).validate_python(s3_file_id)
            )
        return None

    provided_file_id_fmd = await _get_fmd(conn, file_id)
    if provided_file_id_fmd:
        # file_meta_data exists it is not a directory
        return None

    directory_file_id_str: str = get_simcore_directory(file_id)
    if directory_file_id_str == "":
        # could not extract a directory name from the provided path
        return None

    directory_file_id = TypeAdapter(SimcoreS3FileID).validate_python(
        directory_file_id_str
    )
    directory_file_id_fmd = await _get_fmd(conn, directory_file_id)

    return directory_file_id if directory_file_id_fmd else None


def compute_file_id_prefix(file_id: str, levels: int):
    components = file_id.strip("/").split("/")
    return "/".join(components[:levels])


async def list_child_paths_from_s3(
    s3_client: SimcoreS3API,
    *,
    dir_fmd: FileMetaData,
    bucket: S3BucketName,
    file_filter: Path,
    limit: int,
    cursor: GenericCursor | None,
) -> tuple[list[PathMetaData], GenericCursor | None]:
    """list direct children given by `file_filter` of a directory.
    Tries first using file_filter as a full path, if not results are found will
    try using file_filter as a partial prefix.
    """
    objects_cursor = None
    if cursor is not None:
        cursor_params = orjson.loads(cursor)
        assert cursor_params["file_filter"] == f"{file_filter}"  # nosec
        objects_cursor = cursor_params["objects_next_cursor"]
    list_s3_objects, objects_next_cursor = await s3_client.list_objects(
        bucket=bucket,
        prefix=file_filter,
        start_after=None,
        limit=limit,
        next_cursor=objects_cursor,
        is_partial_prefix=False,
    )
    if not list_s3_objects:
        list_s3_objects, objects_next_cursor = await s3_client.list_objects(
            bucket=bucket,
            prefix=file_filter,
            start_after=None,
            limit=limit,
            next_cursor=objects_cursor,
            is_partial_prefix=True,
        )

    paths_metadata = [
        PathMetaData.from_s3_object_in_dir(s3_object, dir_fmd)
        for s3_object in list_s3_objects
    ]
    next_cursor = None
    if objects_next_cursor:
        next_cursor = orjson.dumps(
            {
                "file_filter": f"{file_filter}",
                "objects_next_cursor": objects_next_cursor,
            }
        )

    return paths_metadata, next_cursor


async def list_child_paths_from_repository(
    conn: AsyncConnection,
    *,
    filter_by_project_ids: list[ProjectID] | None,
    filter_by_file_prefix: Path | None,
    cursor: GenericCursor | None,
    limit: int,
) -> tuple[list[PathMetaData], GenericCursor | None, file_meta_data.TotalChildren]:
    paths_metadata, next_cursor, total = await file_meta_data.list_child_paths(
        conn,
        filter_by_project_ids=filter_by_project_ids,
        filter_by_file_prefix=filter_by_file_prefix,
        limit=limit,
        cursor=cursor,
        is_partial_prefix=False,
    )
    if not paths_metadata:
        paths_metadata, next_cursor, total = await file_meta_data.list_child_paths(
            conn,
            filter_by_project_ids=filter_by_project_ids,
            filter_by_file_prefix=filter_by_file_prefix,
            limit=limit,
            cursor=cursor,
            is_partial_prefix=True,
        )

    return paths_metadata, next_cursor, total
