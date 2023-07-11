from aiohttp import web
from models_library.api_schemas_storage import S3BucketName
from models_library.projects_nodes_io import SimcoreS3DirectoryID, SimcoreS3FileID
from pydantic import ByteSize, NonNegativeInt, parse_obj_as
from servicelib.utils import ensure_ends_with

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


def get_simcore_directory(file_id: SimcoreS3FileID) -> str:
    try:
        directory_id = SimcoreS3DirectoryID.from_simcore_s3_object(file_id)
    except ValueError:
        return ""
    return f"{directory_id}"
