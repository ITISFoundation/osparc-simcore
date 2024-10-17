import os
from pathlib import Path

from pydantic import ByteSize, TypeAdapter


def get_directory_total_size(path: Path) -> ByteSize:
    """return the size of a directory in bytes"""
    # NOTE: performance of this degrades with large amounts of files
    # until we do not hit 1 million it can be ignored
    # NOTE: file size has no impact on performance
    if not path.exists():
        return TypeAdapter(ByteSize).validate_python(0)

    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += get_directory_total_size(Path(entry.path))
    return TypeAdapter(ByteSize).validate_python(total)
