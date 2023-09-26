from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from pydantic import ByteSize, parse_obj_as
from servicelib.archiving_utils import archive_dir, unarchive_dir
from servicelib.file_utils import (
    USER_PREFERENCES_MAX_SIZE_KB,
    get_temporary_path_name,
    remove_directory,
)

from ._errors import DestinationIsNotADirectoryError, PreferencesAreTooBigError

_MAX_PREFERENCES_TOTAL_SIZE: Final[ByteSize] = parse_obj_as(
    ByteSize, f"{USER_PREFERENCES_MAX_SIZE_KB}kib"
)


@asynccontextmanager
async def _temporary_path_name() -> AsyncIterator[Path]:
    temporary_path = get_temporary_path_name()
    try:
        yield temporary_path
    finally:
        if temporary_path.exists():
            if temporary_path.is_file():
                temporary_path.unlink()
            else:
                await remove_directory(temporary_path)


async def dir_to_bytes(source: Path) -> bytes:
    if not source.is_dir():
        raise DestinationIsNotADirectoryError(source)

    async with _temporary_path_name() as archive_path:
        await archive_dir(source, archive_path, compress=True, store_relative_path=True)

        archive_size = archive_path.stat().st_size
        if archive_size > _MAX_PREFERENCES_TOTAL_SIZE:
            raise PreferencesAreTooBigError(archive_size, _MAX_PREFERENCES_TOTAL_SIZE)

        return archive_path.read_bytes()


async def dir_from_bytes(payload: bytes, destination: Path) -> None:
    if not destination.is_dir():
        raise DestinationIsNotADirectoryError(destination)

    await remove_directory(destination, only_children=True)

    async with _temporary_path_name() as archive_path:
        archive_path.write_bytes(payload)
        await unarchive_dir(archive_path, destination)
