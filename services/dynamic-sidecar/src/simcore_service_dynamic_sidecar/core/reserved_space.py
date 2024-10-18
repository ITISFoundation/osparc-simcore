import os
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from pydantic import ByteSize, TypeAdapter

from .settings import ApplicationSettings

_RESERVED_DISK_SPACE_NAME: Final[Path] = Path(
    "/tmp/reserved_disk_space"  # nosec # noqa: S108
)
_DEFAULT_CHUNK_SIZE: Final[ByteSize] = TypeAdapter(ByteSize).validate_python("8k")


def _write_random_binary_file(
    file_path: Path, total_size: ByteSize, *, chunk_size: ByteSize = _DEFAULT_CHUNK_SIZE
):
    with Path.open(file_path, "wb") as file:
        bytes_written: int = 0
        while bytes_written < total_size:
            # Calculate the size of the current chunk
            remaining_size = total_size - bytes_written
            current_chunk_size = min(chunk_size, remaining_size)

            binary_data = os.urandom(current_chunk_size)
            file.write(binary_data)
            bytes_written += current_chunk_size


def remove_reserved_disk_space() -> None:
    _RESERVED_DISK_SPACE_NAME.unlink(missing_ok=True)


def setup(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    _write_random_binary_file(
        _RESERVED_DISK_SPACE_NAME, settings.DYNAMIC_SIDECAR_RESERVED_SPACE_SIZE
    )
