from pathlib import Path
from .pools import async_on_threadpool
import os


async def remove_directory(path: Path, only_children: bool = False) -> None:
    """Optional parameter allows to remove all children and keep directory"""
    if not path.is_dir():
        raise ValueError(f"Provided path={path} must be a directory")

    command = f"rm -r {path}/*" if only_children else f"rm -r {path}"
    await async_on_threadpool(lambda: os.system(command))
