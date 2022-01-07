import asyncio
import shutil
from pathlib import Path

# https://docs.python.org/3/library/shutil.html#shutil.rmtree
# https://docs.python.org/3/library/os.html#os.remove
from aiofiles.os import remove
from aiofiles.os import wrap as sync_to_async

_shutil_rmtree = sync_to_async(shutil.rmtree)


async def _rm(path: Path):
    """Removes file or directory"""
    try:
        await remove(path)
    except IsADirectoryError:
        await _shutil_rmtree(path, ignore_errors=True)


async def remove_directory(
    path: Path, only_children: bool = False, missing_ok: bool = False
) -> None:
    """Optional parameter allows to remove all children and keep directory"""
    if not path.exists():
        if missing_ok:
            return

        raise FileNotFoundError(f"No such file or directory {path}")

    if not path.is_dir():
        raise NotADirectoryError(f"Provided path={path} must be a directory")

    if only_children:
        await asyncio.gather(*[_rm(child) for child in path.glob("*")])
    else:
        await _shutil_rmtree(path, onerror=missing_ok)
