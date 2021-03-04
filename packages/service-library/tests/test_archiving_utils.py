# pylint:disable=redefined-outer-name,unused-argument

import os
import tempfile
import hashlib
import random
from pathlib import Path
import asyncio
from typing import Set, List, Dict, Iterator, Tuple
from concurrent.futures import ProcessPoolExecutor
import string
import secrets


import pytest

from servicelib.archiving_utils import archive_dir, unarchive_dir


@pytest.fixture
def temp_dir_one() -> Path:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def temp_dir_two(tmpdir) -> Path:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def dir_with_random_content() -> Path:
    def random_string(length: int) -> str:
        return "".join(secrets.choice(string.ascii_letters) for i in range(length))

    def make_files_in_dir(dir_path: Path, file_count: int) -> None:
        for _ in range(file_count):
            (dir_path / f"{random_string(8)}.bin").write_bytes(
                os.urandom(random.randint(1, 10))
            )

    def ensure_dir(path_to_ensure: Path) -> Path:
        path_to_ensure.mkdir(parents=True, exist_ok=True)
        return path_to_ensure

    def make_subdirectory_with_content(subdir_name: Path, max_file_count: int) -> None:
        subdir_name = ensure_dir(subdir_name)
        make_files_in_dir(
            dir_path=subdir_name,
            file_count=random.randint(1, max_file_count),
        )

    def make_subdirectories_with_content(
        subdir_name: Path, max_subdirectories_count: int, max_file_count: int
    ) -> None:
        subdirectories_count = random.randint(1, max_subdirectories_count)
        for _ in range(subdirectories_count):
            make_subdirectory_with_content(
                subdir_name=subdir_name / f"{random_string(4)}",
                max_file_count=max_file_count,
            )

    def get_dirs_and_subdris_in_path(path_to_scan: Path) -> Iterator[Path]:
        return [path for path in path_to_scan.rglob("*") if path.is_dir()]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        data_container = ensure_dir(temp_dir_path / "study_data")

        make_subdirectories_with_content(
            subdir_name=data_container, max_subdirectories_count=5, max_file_count=5
        )
        make_files_in_dir(dir_path=data_container, file_count=5)

        # creates a good amount of files
        for _ in range(4):
            for subdirectory_path in get_dirs_and_subdris_in_path(data_container):
                make_subdirectories_with_content(
                    subdir_name=subdirectory_path,
                    max_subdirectories_count=3,
                    max_file_count=3,
                )

        yield temp_dir_path


def strip_directory_from_path(input_path: Path, to_strip: Path) -> Path:
    to_strip = f"{str(to_strip)}/"
    return Path(str(input_path).replace(to_strip, ""))


def get_all_files_in_dir(dir_path: Path) -> Set[Path]:
    return {
        strip_directory_from_path(x, dir_path)
        for x in dir_path.rglob("*")
        if x.is_file()
    }


def _compute_hash(file_path: Path) -> Tuple[Path, str]:
    with open(file_path, "rb") as file_to_hash:
        file_hash = hashlib.md5()
        chunk = file_to_hash.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = file_to_hash.read(8192)

    return file_path, file_hash.hexdigest()


async def compute_hashes(file_paths: List[Path]) -> Dict[Path, str]:
    """given a list of files computes hashes for the files on a process pool"""

    loop = asyncio.get_event_loop()

    with ProcessPoolExecutor() as prcess_pool_executor:
        tasks = [
            loop.run_in_executor(prcess_pool_executor, _compute_hash, file_path)
            for file_path in file_paths
        ]
        # pylint: disable=unnecessary-comprehension
        # see return value of _compute_hash it is a tuple, mapping list[Tuple[Path,str]] to Dict[Path, str] here
        return {k: v for k, v in await asyncio.gather(*tasks)}


def full_file_path_from_dir_and_subdirs(dir_path: Path) -> List[Path]:
    return [x for x in dir_path.rglob("*") if x.is_file()]


async def assert_same_directory_content(
    dir_to_compress: Path, output_dir: Path, inject_relative_path: Path = None
) -> None:
    def _relative_path(input_path: Path) -> Path:
        return Path(str(inject_relative_path / str(input_path))[1:])

    input_set = get_all_files_in_dir(dir_to_compress)
    output_set = get_all_files_in_dir(output_dir)

    if inject_relative_path is not None:
        input_set = {_relative_path(x) for x in input_set}

    assert (
        input_set == output_set
    ), f"There following files are missing {input_set - output_set}"

    # computing the hashes for dir_to_compress and map in a dict
    # with the name starting from the root of the directory and md5sum
    dir_to_compress_hashes = {
        strip_directory_from_path(k, dir_to_compress): v
        for k, v in (
            await compute_hashes(full_file_path_from_dir_and_subdirs(dir_to_compress))
        ).items()
    }

    # computing the hashes for output_dir and map in a dict
    # with the name starting from the root of the directory and md5sum
    output_dir_hashes = {
        strip_directory_from_path(k, output_dir): v
        for k, v in (
            await compute_hashes(full_file_path_from_dir_and_subdirs(output_dir))
        ).items()
    }

    # finally check if hashes are mapped 1 to 1 in order to verify
    # that the compress/decompress worked correctly
    for key in dir_to_compress_hashes:
        assert (
            dir_to_compress_hashes[key]
            == output_dir_hashes[_relative_path(key) if inject_relative_path else key]
        )


# end utils


@pytest.mark.parametrize("compress", [True, False])
async def test_archive_unarchive_same_structure_dir(
    dir_with_random_content: Path,
    temp_dir_one: Path,
    temp_dir_two: Path,
    compress: bool,
):
    archive_file = temp_dir_one / "archive.zip"

    archive_result = await archive_dir(
        dir_to_compress=dir_with_random_content,
        destination=archive_file,
        store_relative_path=True,
        compress=compress,
    )
    assert archive_result is True

    await unarchive_dir(
        archive_to_extract=archive_file, destination_folder=temp_dir_two
    )

    await assert_same_directory_content(dir_with_random_content, temp_dir_two)


@pytest.mark.parametrize("compress", [True, False])
async def test_archive_unarchive_include_relative_paths(
    dir_with_random_content: Path,
    temp_dir_one: Path,
    temp_dir_two: Path,
    compress: bool,
):
    archive_file = temp_dir_one / "archive.zip"

    archive_result = await archive_dir(
        dir_to_compress=dir_with_random_content,
        destination=archive_file,
        store_relative_path=False,
        compress=False,
    )
    assert archive_result is True

    await unarchive_dir(
        archive_to_extract=archive_file, destination_folder=temp_dir_two
    )

    await assert_same_directory_content(
        dir_with_random_content, temp_dir_two, dir_with_random_content
    )
