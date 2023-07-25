import asyncio
import shutil
from pathlib import Path

# https://docs.python.org/3/library/shutil.html#shutil.rmtree
# https://docs.python.org/3/library/os.html#os.remove
from aiofiles.os import remove
from aiofiles.os import wrap as sync_to_async  # type: ignore[attr-defined]

_shutil_rmtree = sync_to_async(shutil.rmtree)


async def _rm(path: Path, ignore_errors: bool):
    """Removes file or directory"""
    try:
        await remove(path)
    except IsADirectoryError:
        await _shutil_rmtree(path, ignore_errors=ignore_errors)


async def remove_directory(
    path: Path, only_children: bool = False, ignore_errors: bool = False
) -> None:
    """Optional parameter allows to remove all children and keep directory"""
    if only_children:
        await asyncio.gather(*[_rm(child, ignore_errors) for child in path.glob("*")])
    else:
        await _shutil_rmtree(path, ignore_errors=ignore_errors)
