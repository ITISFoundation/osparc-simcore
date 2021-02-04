# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import hashlib
import tempfile
from pathlib import Path
from pprint import pprint
from uuid import uuid4

import pytest
from fastapi import UploadFile
from models_library.api_schemas_storage import FileMetaData as StorageFileMetaData
from pydantic import ValidationError
from simcore_service_api_server.api.routes.files import convert_metadata
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


def test_convert_filemetadata():

    storage_file_meta = StorageFileMetaData(
        **StorageFileMetaData.Config.schema_extra["examples"][1]
    )
    storage_file_meta.file_id = f"api/{uuid4()}/extensionless"
    apiserver_file_meta = convert_metadata(storage_file_meta)

    assert apiserver_file_meta.file_id
    assert apiserver_file_meta.filename == "extensionless"
    assert apiserver_file_meta.content_type is None
    assert apiserver_file_meta.checksum == storage_file_meta.entity_tag

    with pytest.raises(ValueError):
        storage_file_meta.file_id = f"{uuid4()}/{uuid4()}/foo.txt"
        convert_metadata(storage_file_meta)

    with pytest.raises(ValidationError):
        storage_file_meta.file_id = "api/NOTUUID/foo.txt"
        convert_metadata(storage_file_meta)


@pytest.mark.parametrize("model_cls", (FileMetadata,))
def test_file_model_examples(model_cls, model_cls_examples):
    for example in model_cls_examples:
        pprint(example)
        model_instance = model_cls(**example)
        assert model_instance
