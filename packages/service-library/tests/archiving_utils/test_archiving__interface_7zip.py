# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from pathlib import Path

import pytest
from helpers import print_tree
from pydantic import NonNegativeInt
from servicelib.archiving_utils._interface_7zip import (
    _7ZipProgressParser,
    _extract_file_names_from_archive,
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

    async def _progress_handler(byte_progress: NonNegativeInt) -> None:
        detected_entries.append(byte_progress)

    parser = _7ZipProgressParser(_progress_handler)
    for chunk in stdout_entries:
        await parser.parse_chunk(chunk)

    print(detected_entries)
    assert sum(detected_entries) == expected_size


def _assert_same_folder_content(f1: Path, f2: Path) -> None:
    in_f1 = {x.relative_to(f1) for x in f1.rglob("*")}
    in_f2 = {x.relative_to(f2) for x in f2.rglob("*")}
    assert in_f1 == in_f2


@pytest.mark.parametrize("compress", [True, False])
async def test_archive_unarchive(
    mixed_file_types: Path, archive_path: Path, unpacked_archive: Path, compress: bool
):
    await archive_dir(mixed_file_types, archive_path, compress=compress)
    await unarchive_dir(archive_path, unpacked_archive)
    _assert_same_folder_content(mixed_file_types, unpacked_archive)


@pytest.fixture
def empty_folder(tmp_path: Path) -> Path:
    path = tmp_path / "empty_folder"
    path.mkdir()
    return path


@pytest.mark.parametrize("compress", [True, False])
async def test_archive_unarchive_empty_folder(
    empty_folder: Path, archive_path: Path, unpacked_archive: Path, compress: bool
):
    await archive_dir(empty_folder, archive_path, compress=compress)
    await unarchive_dir(archive_path, unpacked_archive)
    _assert_same_folder_content(empty_folder, unpacked_archive)


@pytest.mark.parametrize(
    "file_name, expected_file_count",
    [
        ("list_edge_case.txt", 3),
        ("list_stdout.txt", 674),
        ("list_broken_format.txt", 22),
        ("list_empty_archive.txt", 0),
    ],
)
def test__extract_file_names_from_archive(
    data_archive_utils: Path, file_name: str, expected_file_count: NonNegativeInt
):
    archive_list_stdout_path = data_archive_utils / file_name
    assert archive_list_stdout_path.exists()

    archive_list_stdout_path.read_text()
    files = _extract_file_names_from_archive(archive_list_stdout_path.read_text())
    assert len(files) == expected_file_count


@pytest.mark.parametrize("compress", [True, False])
async def test_archive_unarchive_with_names_with_spaces(tmp_path: Path, compress: bool):
    to_archive_path = tmp_path / "'source of files!a ads now strange'"
    to_archive_path.mkdir(parents=True, exist_ok=True)
    assert to_archive_path.exists()

    # generate some content
    for i in range(10):
        (to_archive_path / f"f{i}.txt").write_text("*" * i)
    print_tree(to_archive_path)

    archive_path = tmp_path / "archived version herre!)!(/£)!'"
    assert not archive_path.exists()

    extracted_to_path = tmp_path / "this is where i want them to be extracted to''''"
    extracted_to_path.mkdir(parents=True, exist_ok=True)
    assert extracted_to_path.exists()

    # source and destination all with spaces
    await archive_dir(to_archive_path, archive_path, compress=compress)
    await unarchive_dir(archive_path, extracted_to_path)
    _assert_same_folder_content(to_archive_path, extracted_to_path)
