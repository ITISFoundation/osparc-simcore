# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from pathlib import Path

import pytest
from pydantic import NonNegativeInt
from servicelib.archiving_utils._interface_7zip import (
    ProgressParser,
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
def compress_stdout(package_tests_dir: Path) -> list[str]:
    path = package_tests_dir / "data" / "archive_utils" / "compress_stdout.json"
    assert path.exists()
    return json.loads(path.read_text())


@pytest.fixture
def decompress_stdout(package_tests_dir: Path) -> list[str]:
    path = package_tests_dir / "data" / "archive_utils" / "decompress_stdout.json"
    assert path.exists()
    return json.loads(path.read_text())


async def test_compress_progress_parser(compress_stdout: list[str]):
    detected_entries: list[NonNegativeInt] = []

    async def progress_handler(byte_progress: NonNegativeInt) -> None:
        detected_entries.append(byte_progress)

    parser = ProgressParser(progress_handler)
    for chunk in compress_stdout:
        await parser.parse_chunk(chunk)

    print(detected_entries)
    assert sum(detected_entries) == 434866026


# TODO: unify these 2 tests since they just use some ["compress_stdout.json", "decompress_stdout.json"] and expected sizes at the end of the day
async def test_decompress_progress_parser(decompress_stdout: list[str]):
    detected_entries: list[NonNegativeInt] = []
    # TODO: als an expected length of [detected_entries] would be ideal to make sure all 100% entries are found

    async def progress_handler(byte_progress: NonNegativeInt) -> None:
        detected_entries.append(byte_progress)

    parser = ProgressParser(progress_handler)
    for chunk in decompress_stdout:
        await parser.parse_chunk(chunk)

    print(detected_entries)
    assert sum(detected_entries) == 434902745


async def test_something(
    mixed_file_types: Path, archive_path: Path, unpacked_archive: Path
):
    await archive_dir(
        mixed_file_types, archive_path, compress=True, store_relative_path=True
    )

    await unarchive_dir(archive_path, unpacked_archive)
