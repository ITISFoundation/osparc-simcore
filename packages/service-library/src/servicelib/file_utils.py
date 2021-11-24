import asyncio
from pathlib import Path


async def remove_directory(path: Path, only_children: bool = False) -> None:
    """Optional parameter allows to remove all children and keep directory"""
    if not path.is_dir():
        raise NotADirectoryError(f"Provided path={path} must be a directory")

    command = f"rm -r {path}/*" if only_children else f"rm -r {path}"

    process = await asyncio.create_subprocess_exec(*command.split(" "))
    await process.wait()
