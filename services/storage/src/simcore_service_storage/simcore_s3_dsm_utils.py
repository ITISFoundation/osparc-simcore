from contextlib import suppress
from pathlib import Path

from aiopg.sa.connection import SAConnection
from aws_library.s3 import S3MetaData, SimcoreS3API
from models_library.api_schemas_storage import S3BucketName
from models_library.projects_nodes_io import (
    SimcoreS3DirectoryID,
    SimcoreS3FileID,
    StorageFileID,
)
from pydantic import ByteSize, NonNegativeInt, TypeAdapter
from servicelib.utils import ensure_ends_with

from . import db_file_meta_data
from .exceptions import FileMetaDataNotFoundError
from .models import FileMetaData, FileMetaDataAtDB
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
    conn: SAConnection, file_id: SimcoreS3FileID
) -> SimcoreS3FileID | None:
    """
    returns the containing file's `directory_file_id` if the entry exists
    in the `file_meta_data` table
    """

    async def _get_fmd(
        conn: SAConnection, s3_file_id: StorageFileID
    ) -> FileMetaDataAtDB | None:
        with suppress(FileMetaDataNotFoundError):
            return await db_file_meta_data.get(
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
