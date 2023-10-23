# pylint: disable=redefined-outer-name

import filecmp
from pathlib import Path

import pytest
from simcore_service_dynamic_sidecar.modules.user_services_preferences._errors import (
    DestinationIsNotADirectoryError,
    PreferencesAreTooBigError,
)
from simcore_service_dynamic_sidecar.modules.user_services_preferences._packaging import (
    dir_from_bytes,
    dir_to_bytes,
)


def _make_dir(tmp_path: Path, dir_name: str) -> Path:
    target_path = tmp_path / dir_name
    target_path.mkdir(parents=True, exist_ok=True)
    assert target_path.is_dir()
    assert len(list(target_path.rglob("*"))) == 0
    return target_path


def _get_relative_file_paths(path: Path) -> set[Path]:
    return {x.relative_to(path) for x in path.rglob("*") if x.is_file()}


def assert_same_files(dir1: Path, dir2: Path):
    assert dir1.is_dir()
    assert dir2.is_dir()

    files_in_dir1 = _get_relative_file_paths(dir1)
    files_in_dir2 = _get_relative_file_paths(dir2)

    assert files_in_dir1 == files_in_dir2

    for file_name in files_in_dir1:
        assert filecmp.cmp(dir1 / file_name, dir2 / file_name)


@pytest.fixture
def source_path(tmp_path: Path) -> Path:
    return _make_dir(tmp_path, "soruce_path")


@pytest.fixture
def from_bytes_path(tmp_path: Path) -> Path:
    return _make_dir(tmp_path, "from_bytes_path")


def add_files_in_dir(path: Path, file_count: int, subdirs_count: int) -> None:
    assert subdirs_count > 0
    path.mkdir(parents=True, exist_ok=True)
    for s in range(subdirs_count):
        (path / f"subdir{s}").mkdir(parents=True, exist_ok=True)
        for f in range(file_count):
            (path / f"subdir{s}" / f"f{f}.txt").write_text(f"{f} and some text")


async def test_workflow(source_path: Path, from_bytes_path: Path):
    add_files_in_dir(source_path, file_count=10, subdirs_count=1)

    payload = await dir_to_bytes(source_path)
    assert len(payload) > 0

    await dir_from_bytes(payload, from_bytes_path)

    assert_same_files(source_path, from_bytes_path)


async def test_dir_to_bytes_too_big(source_path: Path):
    add_files_in_dir(source_path, file_count=500, subdirs_count=10)

    with pytest.raises(PreferencesAreTooBigError):
        await dir_to_bytes(source_path)


async def test_destination_is_not_a_directory(tmp_path: Path):
    a_file = tmp_path / "a_file"
    a_file.write_text("a")

    with pytest.raises(DestinationIsNotADirectoryError):
        await dir_to_bytes(a_file)

    with pytest.raises(DestinationIsNotADirectoryError):
        await dir_from_bytes(b"", a_file)
