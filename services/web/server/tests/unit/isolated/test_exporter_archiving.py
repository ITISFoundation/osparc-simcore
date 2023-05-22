# pylint:disable=redefined-outer-name,unused-argument

import tempfile
import uuid
from pathlib import Path
from typing import Iterator

import pytest
from simcore_service_webserver.exporter.archiving import zip_folder
from simcore_service_webserver.exporter.exceptions import ExporterException


@pytest.fixture
def temp_dir(tmpdir) -> Path:
    # cast to Path object
    return Path(tmpdir)


@pytest.fixture
def temp_dir2() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        extract_dir_path = temp_dir_path / "extract_dir"
        extract_dir_path.mkdir(parents=True, exist_ok=True)
        yield extract_dir_path


@pytest.fixture
def temp_file(tmp_path: Path) -> Iterator[Path]:
    file_path = tmp_path / "file"
    file_path.write_text("test_data")
    yield file_path
    file_path.unlink()


@pytest.fixture
def project_uuid():
    return str(uuid.uuid4())


def temp_dir_with_existing_archive(temp_dir, project_uui) -> Path:
    nested_dir = temp_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir / "archive.zip"
    nested_file.write_text("some_data")

    return nested_dir


async def test_archive_already_exists(temp_dir, project_uuid):
    tmp_dir_to_compress = temp_dir_with_existing_archive(temp_dir, project_uuid)
    with pytest.raises(ExporterException) as exc_info:
        await zip_folder(
            folder_to_zip=tmp_dir_to_compress, destination_folder=tmp_dir_to_compress
        )

    assert exc_info.type is ExporterException
    assert (
        exc_info.value.args[0]
        == f"Cannot archive '{temp_dir}/nested' because '{str(temp_dir)}/nested/archive.zip' already exists"
    )
