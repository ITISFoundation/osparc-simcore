from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from servicelib.archiving_utils import archive_dir
from servicelib.file_utils import get_temporary_path_name, remove_directory


async def to_binary(source_path: Path) -> bytes:
    ...


@asynccontextmanager
async def temporary_path_name() -> AsyncIterator[Path]:
    temporary_path = get_temporary_path_name()
    try:
        yield temporary_path
    finally:
        if temporary_path.exists():
            if temporary_path.is_file():
                temporary_path.unlink()
            else:
                await remove_directory(temporary_path)


async def from_bytes(payload: bytes, destination_to: Path) -> None:
    if not destination_to.is_dir():
        msg = f"Provided {destination_to=} must be a directory"
        raise RuntimeError(msg)

    await remove_directory(destination_to, only_children=True)

    async with temporary_path_name() as tmp_path:
        await archive_dir(
            destination_to, tmp_path, compress=True, store_relative_path=True
        )

        # check size of file and raise error if too big!
