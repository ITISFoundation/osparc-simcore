from contextlib import suppress

from aiohttp import web
from aiopg.sa.connection import SAConnection
from models_library.api_schemas_storage import S3BucketName
from models_library.projects_nodes_io import (
    SimcoreS3DirectoryID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.users import UserID
from pydantic import ByteSize, NonNegativeInt, parse_obj_as
from servicelib.utils import ensure_ends_with

from . import db_file_meta_data
from .db_access_layer import AccessRights, get_file_access_rights
from .exceptions import FileAccessRightError, FileMetaDataNotFoundError
from .models import FileMetaData, FileMetaDataAtDB
from .s3 import get_s3_client
from .s3_client import S3MetaData
from .utils import convert_db_to_model


async def expand_directory(
    app: web.Application,
    simcore_bucket_name: S3BucketName,
    fmd: FileMetaDataAtDB,
    max_items_to_include: NonNegativeInt,
) -> list[FileMetaData]:
    """
    Scans S3 backend and returns a list S3MetaData entries which get mapped
    to FileMetaData entry.
    """
    files_in_folder: list[S3MetaData] = await get_s3_client(app).list_files(
        simcore_bucket_name,
        prefix=ensure_ends_with(fmd.file_id, "/"),
        max_files_to_list=max_items_to_include,
    )
    result: list[FileMetaData] = [
        convert_db_to_model(
            FileMetaDataAtDB(
                location_id=fmd.location_id,
                location=fmd.location,
                bucket_name=fmd.bucket_name,
                object_name=x.file_id,
                user_id=fmd.user_id,
                # NOTE: to ensure users have a consistent experience the
                # `created_at` field is inherited from the last_modified
                # coming from S3. This way if a file is created 1 month after the
                # creation of the directory, the file's creation date
                # will not be 1 month in the passed.
                created_at=x.last_modified,
                file_id=x.file_id,
                file_size=parse_obj_as(ByteSize, x.size),
                last_modified=x.last_modified,
                entity_tag=x.e_tag,
                is_soft_link=False,
                is_directory=False,
            )
        )
        for x in files_in_folder
    ]
    return result


def get_simcore_directory(file_id: StorageFileID) -> str:
    try:
        directory_id = SimcoreS3DirectoryID.from_simcore_s3_object(file_id)
    except ValueError:
        return ""
    return f"{directory_id}"


async def get_directory_file_id(
    conn: SAConnection, file_id: StorageFileID
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
                conn, parse_obj_as(SimcoreS3FileID, s3_file_id)
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

    directory_file_id = parse_obj_as(SimcoreS3FileID, directory_file_id_str.rstrip("/"))
    directory_file_id_fmd = await _get_fmd(conn, directory_file_id)

    return directory_file_id if directory_file_id_fmd else None


async def ensure_read_access_rights(
    conn: SAConnection, user_id: UserID, storage_file_id: StorageFileID
) -> None:
    """
    Raises:
        FileAccessRightError
    """
    can: AccessRights | None = await get_file_access_rights(
        conn, user_id, storage_file_id
    )
    if not can.read:
        # NOTE: this is tricky. A user with read access can download and data!
        # If write permission would be required, then shared projects as views cannot
        # recover data in nodes (e.g. jupyter cannot pull work data)
        #
        raise FileAccessRightError(access_right="read", file_id=storage_file_id)
