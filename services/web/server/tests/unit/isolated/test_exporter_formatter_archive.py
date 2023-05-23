# pylint:disable=redefined-outer-name

import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from faker import Faker
from simcore_service_webserver.exporter.exceptions import SDSException
from simcore_service_webserver.exporter.formatter.archive import _compress_dir


@pytest.fixture
def temp_dir(tmpdir) -> Path:
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
def project_id(faker: Faker):
    return faker.uuid4()


def temp_dir_with_existing_archive(temp_dir, project_id) -> Path:
    nested_dir = temp_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir / f"sds_{project_id}.zip"
    nested_file.write_text("some_data")
    return nested_dir


async def test_archive_already_exists(temp_dir, project_id):
    tmp_dir_to_compress = temp_dir_with_existing_archive(temp_dir, project_id)
    with pytest.raises(SDSException) as exc_info:
        await _compress_dir(
            folder_to_zip=tmp_dir_to_compress,
            destination_folder=tmp_dir_to_compress,
            project_id=project_id,
        )

    assert exc_info.type is SDSException
    assert (
        exc_info.value.args[0]
        == f"Cannot archive '{temp_dir}/nested' because '{temp_dir}/nested/sds_{project_id}.zip' already exists"
    )
