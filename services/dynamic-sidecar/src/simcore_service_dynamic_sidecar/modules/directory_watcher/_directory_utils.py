import os
from pathlib import Path

from pydantic import PositiveInt


# TODO: ANE -> PC/SAN how can we setup a warning to check if this function is slower than 1 second?
# it will give us an idea if a user is having a very high amount of files and how common this is
def get_dir_size(path: Path) -> PositiveInt:
    """return the size of a directory in bytes"""
    # NOTE: performance of this degrades with large amounts of files
    # until we do not hit 1 million it can be ignored
    # NOTE: file size has no impact on performance
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += get_dir_size(entry.path)  # type: ignore
    return total
