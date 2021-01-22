# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import hashlib
from pathlib import Path

import pytest
from simcore_service_api_server.models.schemas.files import FileUploaded

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_filepath(tmpdir) -> Path:
    path = Path(tmpdir) / "mock_filepath.txt"
    path.write_text("This is a test")
    return path


async def test_create_fileuploaded_from_path(mock_filepath):
    #
    # $ echo -n "This is a test" | md5sum -
    # ce114e4501d2f4e2dcea3e17b546f339  -
    #
    expected_md5sum = "ce114e4501d2f4e2dcea3e17b546f339"
    assert hashlib.md5("This is a test".encode()).hexdigest() == expected_md5sum

    file_meta = await FileUploaded.create_from_path(mock_filepath)
    assert file_meta.checksum == expected_md5sum
