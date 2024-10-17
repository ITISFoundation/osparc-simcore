from pathlib import Path
from typing import Final

import aiofiles
from pydantic import ByteSize, TypeAdapter
from servicelib.archiving_utils import archive_dir, unarchive_dir
from servicelib.file_utils import remove_directory

from ._errors import DestinationIsNotADirectoryError, PreferencesAreTooBigError

_MAX_PREFERENCES_TOTAL_SIZE: Final[ByteSize] = TypeAdapter(ByteSize).validate_python(
    "128kib"
)


async def dir_to_bytes(source: Path) -> bytes:
    if not source.is_dir():
        raise DestinationIsNotADirectoryError(destination_to=source)

    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "archive"

        await archive_dir(source, archive_path, compress=True, store_relative_path=True)

        archive_size = archive_path.stat().st_size
        if archive_size > _MAX_PREFERENCES_TOTAL_SIZE:
            raise PreferencesAreTooBigError(
                size=archive_size, limit=_MAX_PREFERENCES_TOTAL_SIZE
            )

        return archive_path.read_bytes()


async def dir_from_bytes(payload: bytes, destination: Path) -> None:
    if not destination.is_dir():
        raise DestinationIsNotADirectoryError(destination_to=destination)

    await remove_directory(destination, only_children=True)

    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "archive"

        archive_path.write_bytes(payload)
        await unarchive_dir(archive_path, destination)
