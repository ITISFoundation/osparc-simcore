from collections.abc import Iterable
from pathlib import Path
from typing import TypeAlias

import aiofiles
from servicelib.file_utils import create_sha256_checksum
from servicelib.utils import limited_gather

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


def get_files_info_from_itrable(items: Iterable[Path]) -> _FilesInfo:
    return {f.name: f for f in items if f.is_file()}


async def assert_same_contents(file_info1: _FilesInfo, file_info2: _FilesInfo) -> None:
    assert set(file_info1.keys()) == set(file_info2.keys())

    await limited_gather(
        *(
            assert_same_file_content(file_info1[file_name], file_info2[file_name])
            for file_name in file_info1
        ),
        limit=10,
    )
