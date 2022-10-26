import os
from pathlib import Path

from pydantic import PositiveInt


def get_dir_size(path: Path) -> PositiveInt:
    """return the size of a directory in bytes"""
    total = 0
    for entry in os.scandir(path):
        if entry.is_file():
            total += entry.stat().st_size
        elif entry.is_dir():
            total += get_dir_size(entry.path)
    return total
