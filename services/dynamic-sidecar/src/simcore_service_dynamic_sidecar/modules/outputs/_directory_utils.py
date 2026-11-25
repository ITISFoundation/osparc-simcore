import os
from contextlib import suppress
from pathlib import Path

from pydantic import ByteSize, TypeAdapter


def get_directory_total_size(path: Path) -> ByteSize:
    """return the total size of regular files under `path`; the walk does not follow symlinks"""
    total = 0
    dir_paths: list[Path | str] = [path]
    # cost grows with the number of entries, not with file sizes
    while dir_paths:
        dir_path = dir_paths.pop()
        with suppress(OSError), os.scandir(dir_path) as it:  # entries vanish and directories turn unreadable
            for entry in it:
                with suppress(OSError):
                    # following a symlink to an ancestor would loop the walk
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        dir_paths.append(entry.path)
    return TypeAdapter(ByteSize).validate_python(total)
