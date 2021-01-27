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


@pytest.mark.skip(reason="dev")
def test_create_filemetadata_from_storage_response():
    from models_library.api_schemas_storage import DatasetMetaData, FileMetaData

    dataset_meta = DatasetMetaData(**DatasetMetaData.Config.schema_extra["examples"][0])
    file_meta = FileMetaData(**FileMetaData.Config.schema_extra["examples"][1])

    api_file_metadata = FileMetadata(
        file_id=file_meta.node_id,
        filename=file_meta.file_name,
        # ??
        content_type=None,
        # etag?
        checksum=hashlib.sha256(
            f"{file_meta.last_modified}:{file_meta.file_size}".encode("utf-8")
        ).hexdigest(),
    )

    # user
    uid = 44
    uname = "Jack Sparrow"

    # api/files folder per user
    api_id = "74a84992-8c99-47de-b88a-311c068055ea"  # compose with user? ->
    folder_id = ""  # compose with key?
    files_id = "4896730a-f13b-46d3-b020-ddf559b0479f"  # fix, same for all?

    # uploaded
    filename = "foo.hd5"
    fileid = "82c08600-2102-43b0-bb27-01ab5b3d558e"  # given by API

    ds = DatasetMetaData(dataset_id=api_id, display_name="api")

    fm = FileMetaData(
        project_id=api_id,
        project_name="api",
        node_id=files_id,
        node_name="files",
        file_uuid=f"{api_id}/{files_id}/{fileid}",
        file_name=filename,
        user_id=uid,
        user_name=uname,
        raw_file_path="",
    )
