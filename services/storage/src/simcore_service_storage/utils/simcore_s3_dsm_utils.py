from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from aws_library.s3 import S3MetaData, SimcoreS3API
from aws_library.s3._constants import MULTIPART_COPY_THRESHOLD
from models_library.projects_nodes_io import (
    SimcoreS3DirectoryID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.storage_schemas import S3BucketName
from models_library.users import UserID
from pydantic import ByteSize, NonNegativeInt, TypeAdapter
from servicelib.bytes_iters import ArchiveEntries, get_zip_bytes_iter
from servicelib.progress_bar import ProgressBarData
from servicelib.s3_utils import FileLikeBytesIterReader
from servicelib.utils import ensure_ends_with
from sqlalchemy.ext.asyncio import AsyncConnection

from ..exceptions.errors import FileMetaDataNotFoundError
from ..models import FileMetaData, FileMetaDataAtDB
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


def get_random_export_name(user_id: UserID) -> StorageFileID:
    return TypeAdapter(StorageFileID).validate_python(
        f"exports/{user_id}/{uuid4()}.zip"
    )


async def create_and_upload_export(
    s3_client: SimcoreS3API,
    bucket: S3BucketName,
    *,
    source_object_keys: set[StorageFileID],
    destination_object_keys: StorageFileID,
    progress_bar: ProgressBarData | None,
) -> None:
    if progress_bar is None:
        progress_bar = ProgressBarData(
            num_steps=1, description="create and upload export"
        )

    archive_entries: ArchiveEntries = []
    for s3_object in source_object_keys:
        archive_entries.append(
            (
                s3_object,
                await s3_client.get_bytes_streamer_from_object(bucket, s3_object),
            )
        )

    async with progress_bar:
        await s3_client.upload_object_from_file_like(
            bucket,
            destination_object_keys,
            FileLikeBytesIterReader(
                get_zip_bytes_iter(
                    archive_entries,
                    progress_bar=progress_bar,
                    chunk_size=MULTIPART_COPY_THRESHOLD,
                )
            ),
        )
