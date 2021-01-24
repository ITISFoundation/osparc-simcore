# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import hashlib
import tempfile
from pathlib import Path

import pytest
from fastapi import UploadFile
from simcore_service_api_server.models.schemas.files import FileMetadata

pytestmark = pytest.mark.asyncio

FILE_CONTENT = "This is a test"


@pytest.fixture
def mock_filepath(tmpdir) -> Path:
    path = Path(tmpdir) / "mock_filepath.txt"
    path.write_text(FILE_CONTENT)
    return path


@pytest.fixture
def expected_md5sum():
    #
    # $ echo -n "This is a test" | md5sum -
    # ce114e4501d2f4e2dcea3e17b546f339  -
    #
    expected_md5sum = "ce114e4501d2f4e2dcea3e17b546f339"
    assert hashlib.md5(FILE_CONTENT.encode()).hexdigest() == expected_md5sum
    return expected_md5sum


async def test_create_filemetadata_from_path(mock_filepath, expected_md5sum):
    file_meta = await FileMetadata.create_from_path(mock_filepath)
    assert file_meta.checksum == expected_md5sum


async def test_create_filemetadata_from_starlette_uploadfile(
    mock_filepath, expected_md5sum
):
    # WARNING: upload is a wrapper around a file handler that can actually be in memory as well

    # in file
    with open(mock_filepath, "rb") as file:
        upload = UploadFile(mock_filepath.name, file)

        assert upload.file.tell() == 0
        file_meta = await FileMetadata.create_from_uploaded(upload)
        assert upload.file.tell() > 0, "modifies current position is at the end"

        assert file_meta.checksum == expected_md5sum

    # in memory
    # UploadFile constructor: by not passing file, it enforces a tempfile.SpooledTemporaryFile
    upload_in_memory = UploadFile(mock_filepath.name)

    assert isinstance(upload_in_memory.file, tempfile.SpooledTemporaryFile)
    await upload_in_memory.write(FILE_CONTENT.encode())

    await upload_in_memory.seek(0)
    assert upload_in_memory.file.tell() == 0

    file_meta = await FileMetadata.create_from_uploaded(upload_in_memory)
    assert upload_in_memory.file.tell() > 0, "modifies current position is at the end"
