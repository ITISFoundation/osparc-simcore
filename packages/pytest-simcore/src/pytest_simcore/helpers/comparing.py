import asyncio
import hashlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TypeAlias

import aiofiles
from servicelib.file_utils import create_sha256_checksum

_FilesInfo: TypeAlias = dict[str, Path]


def get_relative_to(folder: Path, file: Path) -> str:
    return f"{file.relative_to(folder)}"


async def assert_same_file_content(path_1: Path, path_2: Path):
    async with aiofiles.open(path_1, "rb") as f1, aiofiles.open(path_2, "rb") as f2:
        checksum_1 = await create_sha256_checksum(f1)
        checksum_2 = await create_sha256_checksum(f2)
    assert checksum_1 == checksum_2


def get_files_info_from_path(folder: Path) -> _FilesInfo:
    return {get_relative_to(folder, f): f for f in folder.rglob("*") if f.is_file()}


def compute_hash(file_path: Path) -> tuple[Path, str]:
    with Path.open(file_path, "rb") as file_to_hash:
        file_hash = hashlib.md5()  # noqa: S324
        chunk = file_to_hash.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = file_to_hash.read(8192)

    return file_path, file_hash.hexdigest()


async def compute_hashes(file_paths: list[Path]) -> dict[Path, str]:
    """given a list of files computes hashes for the files on a process pool"""

    loop = asyncio.get_event_loop()

    with ProcessPoolExecutor() as prcess_pool_executor:
        tasks = [
            loop.run_in_executor(prcess_pool_executor, compute_hash, file_path)
            for file_path in file_paths
        ]
        # pylint: disable=unnecessary-comprehension
        # see return value of _compute_hash it is a tuple, mapping list[Tuple[Path,str]] to Dict[Path, str] here
        return dict(await asyncio.gather(*tasks))


async def assert_same_contents(file_info1: _FilesInfo, file_info2: _FilesInfo) -> None:
    assert set(file_info1.keys()) == set(file_info2.keys())

    hashes_1 = await compute_hashes(list(file_info1.values()))
    hashes_2 = await compute_hashes(list(file_info2.values()))

    for key in file_info1:
        assert hashes_1[file_info1[key]] == hashes_2[file_info2[key]]
