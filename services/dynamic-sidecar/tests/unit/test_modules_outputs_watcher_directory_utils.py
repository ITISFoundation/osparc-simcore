# pylint:disable=redefined-outer-name

import shutil
import time
from pathlib import Path
from random import randbytes
from typing import Iterable
from uuid import uuid4

import pytest
from _pytest.fixtures import FixtureRequest
from pydantic import NonNegativeInt, PositiveInt
from simcore_service_dynamic_sidecar.modules.outputs_watcher._directory_utils import (
    get_dir_size,
)


def _create_files(path: Path, files: NonNegativeInt) -> PositiveInt:
    assert path.exists() is False
    path.mkdir(parents=True, exist_ok=True)
    total = 0
    for _ in range(files):
        file_path = path / f"f{uuid4()}"
        file_path.write_bytes(randbytes(1))
        total += file_path.stat().st_size
    return total


@pytest.fixture
def directory(tmp_path: Path) -> Iterable[Path]:
    yield tmp_path
    shutil.rmtree(tmp_path)


@pytest.fixture(params=[10, 100, 1000])
def files_per_directory(request: FixtureRequest) -> NonNegativeInt:
    return request.param


@pytest.fixture(params=[10, 100])
def subdirs_per_directory(request: FixtureRequest) -> NonNegativeInt:
    return request.param


@pytest.fixture
def dir_with_files(
    directory: Path,
    files_per_directory: NonNegativeInt,
    subdirs_per_directory: NonNegativeInt,
) -> tuple[Path, PositiveInt]:
    expected_size = 0
    for i in range(subdirs_per_directory):
        expected_size += _create_files(directory / f"d{i}", files_per_directory)

    return directory, expected_size


def test_get_dir_size(dir_with_files: tuple[Path, PositiveInt]):
    path, expected_size = dir_with_files
    start = time.time()
    dir_size = get_dir_size(path)
    runtime = time.time() - start

    print(f"{expected_size=} bytes, {dir_size=} bytes")
    # ~ 2.4 seconds per 1 million files on SSDs
    print(f"runtime {runtime:04}")

    assert expected_size == dir_size
