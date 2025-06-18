# pylint:disable=redefined-outer-name

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from faker import Faker
from simcore_service_webserver.exporter._formatter.archive import _compress_dir
from simcore_service_webserver.exporter.exceptions import SDSException


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
def project_id(faker: Faker):
    return faker.uuid4()


def temp_dir_with_existing_archive(tmp_path, project_id) -> Path:
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir / f"sds_{project_id}.zip"
    nested_file.write_text("some_data")
    return nested_dir


async def test_archive_already_exists(tmp_path, project_id):
    tmp_dir_to_compress = temp_dir_with_existing_archive(tmp_path, project_id)
    with pytest.raises(SDSException) as exc_info:
        await _compress_dir(
            folder_to_zip=tmp_dir_to_compress,
            destination_folder=tmp_dir_to_compress,
            project_id=project_id,
        )

    assert exc_info.type is SDSException
    assert (
        exc_info.value.text
        == f"Cannot archive '{tmp_path}/nested' because '{tmp_path}/nested/sds_{project_id}.zip' already exists"
    )
