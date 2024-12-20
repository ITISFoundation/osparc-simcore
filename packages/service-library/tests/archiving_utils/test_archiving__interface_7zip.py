# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from pathlib import Path

import pytest
from pydantic import NonNegativeInt
from servicelib.archiving_utils._interface_7zip import (
    ProgressParser,
    _extract_files_from_archive,
    archive_dir,
    unarchive_dir,
)


@pytest.fixture
async def archive_path(tmp_path: Path) -> Path:
    return tmp_path / "mixed_types_dir.zip"


@pytest.fixture
def unpacked_archive(tmp_path: Path) -> Path:
    path = tmp_path / "unpacked_dir"
    path.mkdir()
    return path


@pytest.fixture
def data_archive_utils(package_tests_dir: Path) -> Path:
    path = package_tests_dir / "data" / "archive_utils"
    assert path.exists()
    assert path.is_dir()
    return path


@pytest.mark.parametrize(
    "progress_stdout, expected_size",
    [
        ("compress_stdout.json", 434866026),
        ("decompress_stdout.json", 434902745),
    ],
)
async def test_compress_progress_parser(
    data_archive_utils: Path, progress_stdout: str, expected_size: NonNegativeInt
):
    stdout_path = data_archive_utils / progress_stdout
    assert stdout_path.exists()
    stdout_entries: list[str] = json.loads(stdout_path.read_text())

    detected_entries: list[NonNegativeInt] = []

    async def progress_handler(byte_progress: NonNegativeInt) -> None:
        detected_entries.append(byte_progress)

    parser = ProgressParser(progress_handler)
    for chunk in stdout_entries:
        await parser.parse_chunk(chunk)

    print(detected_entries)
    assert sum(detected_entries) == expected_size


@pytest.mark.parametrize("compress", [True, False])
async def test_archive_unarchive(
    mixed_file_types: Path, archive_path: Path, unpacked_archive: Path, compress: bool
):
    await archive_dir(mixed_file_types, archive_path, compress=compress)

    await unarchive_dir(archive_path, unpacked_archive)


def test__extract_files_from_archive(data_archive_utils: Path):
    archive_list_stdout_path = data_archive_utils / "list_stdout.txt"
    assert archive_list_stdout_path.exists()

    archive_list_stdout_path.read_text()
    files = _extract_files_from_archive(archive_list_stdout_path.read_text())
    assert len(files) == 674
