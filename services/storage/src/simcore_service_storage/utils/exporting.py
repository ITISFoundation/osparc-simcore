import datetime
import logging
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_storage import S3BucketName
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call

from ..core.settings import get_application_settings
from ..models import FileMetaData
from ..modules.db import file_meta_data, get_db_engine
from ..modules.s3 import SimcoreS3API, get_s3_client

_logger = logging.getLogger(__name__)


def _get_random_export_name(user_id: UserID) -> StorageFileID:
    return TypeAdapter(StorageFileID).validate_python(
        f"exports/{user_id}/{uuid4()}.zip"
    )


async def _upload_fake_archive(
    s3_client: SimcoreS3API,
    bucket: S3BucketName,
    object_keys: set[StorageFileID],
    uploaded_object_key: StorageFileID,
) -> None:
    # NOTE: this will be replaced with the streaming zip archiver
    with tempfile.NamedTemporaryFile(mode="wt", delete=True) as temp_file:
        temp_file.writelines(object_keys)
        temp_file.flush()
        await s3_client.upload_file(
            bucket=bucket,
            file=Path(temp_file.name),
            object_key=uploaded_object_key,
            bytes_transfered_cb=None,
        )


@validate_call
async def create_s3_export(
    app: FastAPI,
    user_id: UserID,
    object_keys: list[StorageFileID],
) -> StorageFileID:
    uploaded_object_key = _get_random_export_name(user_id)

    s3_client = get_s3_client(app)
    settings = get_application_settings(app)
    db_engine = get_db_engine(app)

    assert settings.STORAGE_S3  # nosec
    bucket_name = settings.STORAGE_S3.S3_BUCKET_NAME

    selected_object_keys: set[StorageFileID] = set()

    for object_key in object_keys:
        async for meta_data_files in s3_client.list_objects_paginated(
            bucket_name, object_key
        ):
            for entry in meta_data_files:
                selected_object_keys.add(entry.object_key)

    _logger.debug("will archive '%s' files", len(selected_object_keys))

    # TODO: replace me with streaming archive
    await _upload_fake_archive(
        s3_client, bucket_name, selected_object_keys, uploaded_object_key
    )

    # inserting file_meta_data entry to allow access via the intrface
    async with db_engine.begin() as connection:
        created_modified_at = datetime.datetime.now(datetime.UTC)
        fmd = TypeAdapter(FileMetaData).validate_python(
            {
                "location": "0",
                "location_id": "0",
                "bucket_name": bucket_name,
                "object_name": uploaded_object_key,
                "file_uuid": uploaded_object_key,
                "file_name": uploaded_object_key,
                "file_id": uploaded_object_key,
                "project_id": None,
                "node_id": None,
                "user_id": user_id,
                "sha256_checksum": None,
                "created_at": created_modified_at,
                "last_modified": created_modified_at,
            }
        )
        await file_meta_data.insert(connection, fmd)

    _logger.debug("export available in path '%s'", uploaded_object_key)

    return uploaded_object_key
