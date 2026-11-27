# pylint:disable=redefined-outer-name

import time
from pathlib import Path
from random import randbytes
from uuid import uuid4

import pytest
from pydantic import NonNegativeInt, PositiveInt
from simcore_service_dynamic_sidecar.modules.outputs._directory_utils import (
    get_directory_total_size,
)


def _create_files(path: Path, files: NonNegativeInt) -> PositiveInt:
    assert path.exists() is False
    path.mkdir(parents=True, exist_ok=True)
    total = 0
    for _ in range(files):
        file_path = path / f"f{uuid4()}"
        file_path.write_bytes(randbytes(1))  # noqa: S311
        total += file_path.stat().st_size
    return total


@pytest.fixture(params=[10, 100, 1000])
def files_per_directory(request: pytest.FixtureRequest) -> NonNegativeInt:
    return request.param


@pytest.fixture(params=[10, 100])
def subdirs_per_directory(request: pytest.FixtureRequest) -> NonNegativeInt:
    return request.param


@pytest.fixture
def dir_with_files(
    tmp_path: Path,
    files_per_directory: NonNegativeInt,
    subdirs_per_directory: NonNegativeInt,
) -> tuple[Path, PositiveInt]:
    expected_size = 0
    for i in range(subdirs_per_directory):
        expected_size += _create_files(tmp_path / f"d{i}", files_per_directory)

    return tmp_path, expected_size


def test_get_directory_total_size(dir_with_files: tuple[Path, PositiveInt]):
    path, expected_size = dir_with_files
    start = time.time()
    dir_size = get_directory_total_size(path)
    runtime = time.time() - start

    print(f"{expected_size=} bytes, {dir_size=} bytes")
    # ~ 2.4 seconds per 1 million files on SSDs
    print(f"runtime {runtime:04}")

    assert expected_size == dir_size


def test_get_directory_total_size_with_symlink_to_ancestor_directory(
    tmp_path: Path,
):
    # the walk must not follow a directory symlink back to an ancestor: ELOOP
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "afile.txt").write_text("data")
    (tmp_path / "sub" / "up").symlink_to(tmp_path)

    assert get_directory_total_size(tmp_path) == len("data")


def test_get_directory_total_size_with_self_looping_symlink(tmp_path: Path):
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    (tmp_path / "afile.txt").write_bytes(b"12345")

    assert get_directory_total_size(tmp_path) == 5

    loop.unlink()


def test_get_directory_total_size_with_broken_symlink(tmp_path: Path):
    (tmp_path / "broken").symlink_to(tmp_path / "missing_target")

    assert get_directory_total_size(tmp_path) == 0


def test_get_directory_total_size_ignores_symlinks_to_targets_outside_the_tree(tmp_path: Path):
    # every entry check passes follow_symlinks=False: a symlink contributes no size, valid or not
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "target.dat").write_bytes(b"1234567890")

    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "real.dat").write_bytes(b"123")
    (tree / "link_to_file").symlink_to(outside / "target.dat")
    (tree / "link_to_dir").symlink_to(outside)

    assert get_directory_total_size(tree) == 3


def test_get_directory_total_size_on_missing_directory(tmp_path: Path):
    assert get_directory_total_size(tmp_path / "does_not_exist") == 0
