# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import hashlib
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import UploadFile
from models_library.api_schemas_storage import FileMetaDataGet as StorageFileMetaData
from models_library.basic_types import MD5Str
from models_library.projects_nodes_io import StorageFileID
from pydantic import ValidationError, parse_obj_as
from simcore_service_api_server.models.schemas.files import File
from simcore_service_api_server.services.storage import to_file_api_model

FILE_CONTENT = "This is a test"


@pytest.fixture
def mock_filepath(tmp_path: Path) -> Path:
    path = tmp_path / "mock_filepath.txt"
    path.write_text(FILE_CONTENT)
    return path


@pytest.fixture
def expected_md5sum() -> MD5Str:
    #
    # $ echo -n "This is a test" | md5sum -
    # ce114e4501d2f4e2dcea3e17b546f339  -
    #
    _md5sum: MD5Str = parse_obj_as(MD5Str, "ce114e4501d2f4e2dcea3e17b546f339")
    assert hashlib.md5(FILE_CONTENT.encode()).hexdigest() == _md5sum
    return _md5sum


async def test_create_filemetadata_from_path(
    mock_filepath: Path, expected_md5sum: MD5Str
):
    file_meta = await File.create_from_path(mock_filepath)
    assert file_meta.e_tag == expected_md5sum


async def test_create_filemetadata_from_starlette_uploadfile(
    mock_filepath: Path, expected_md5sum: MD5Str
):
    # WARNING: upload is a wrapper around a file handler that can actually be in memory as well

    # in file
    with Path.open(mock_filepath, "rb") as fh:
        upload = UploadFile(file=fh, filename=mock_filepath.name)

        assert upload.file.tell() == 0
        file_meta = await File.create_from_uploaded(upload)
        assert upload.file.tell() > 0, "modifies current position is at the end"

        assert file_meta.e_tag == expected_md5sum

    # in memory
    with tempfile.SpooledTemporaryFile() as spooled_tmpfile:
        upload_in_memory = UploadFile(file=spooled_tmpfile, filename=mock_filepath.name)

        assert isinstance(upload_in_memory.file, tempfile.SpooledTemporaryFile)
        await upload_in_memory.write(FILE_CONTENT.encode())

        await upload_in_memory.seek(0)
        assert upload_in_memory.file.tell() == 0

        file_meta = await File.create_from_uploaded(upload_in_memory)
        assert (
            upload_in_memory.file.tell() > 0
        ), "modifies current position is at the end"


def test_convert_between_file_models():
    storage_file_meta = StorageFileMetaData(
        **StorageFileMetaData.Config.schema_extra["examples"][1]
    )
    storage_file_meta.file_id = parse_obj_as(
        StorageFileID, f"api/{uuid4()}/extensionless"
    )
    apiserver_file_meta = to_file_api_model(storage_file_meta)

    assert apiserver_file_meta.id
    assert apiserver_file_meta.filename == "extensionless"
    assert apiserver_file_meta.content_type == "application/octet-stream"  # default
    assert apiserver_file_meta.e_tag == storage_file_meta.entity_tag

    with pytest.raises(ValueError):
        storage_file_meta.file_id = parse_obj_as(
            StorageFileID, f"{uuid4()}/{uuid4()}/foo.txt"
        )
        to_file_api_model(storage_file_meta)

    with pytest.raises(ValidationError):
        storage_file_meta.file_id = parse_obj_as(StorageFileID, "api/NOTUUID/foo.txt")
        to_file_api_model(storage_file_meta)
