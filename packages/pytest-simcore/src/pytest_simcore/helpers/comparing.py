from pathlib import Path
from typing import TypeAlias

import aiofiles
from servicelib.file_utils import create_sha256_checksum

_FilesInFolder: TypeAlias = dict[str, Path]


def get_relative_to(folder: Path, file: Path) -> str:
    return f"{file.relative_to(folder)}"


async def assert_same_file_content(file_1: Path, file_2: Path):
    async with aiofiles.open(file_1, "rb") as f1, aiofiles.open(file_2, "rb") as f2:
        checksum_1 = await create_sha256_checksum(f1)
        checksum_2 = await create_sha256_checksum(f2)
    assert checksum_1 == checksum_2


def get_files_in_folder(folder: Path) -> _FilesInFolder:
    return {get_relative_to(folder, f): f for f in folder.rglob("*") if f.is_file()}


async def assert_same_folder_contents(
    fif1: _FilesInFolder, fif2: _FilesInFolder
) -> None:
    assert set(fif1.keys()) == set(fif2.keys())

    for file_name in fif1:
        await assert_same_file_content(fif1[file_name], fif2[file_name])
