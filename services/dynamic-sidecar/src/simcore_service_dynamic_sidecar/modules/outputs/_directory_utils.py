import os
from contextlib import suppress
from pathlib import Path

from pydantic import ByteSize, TypeAdapter


def get_directory_total_size(path: Path) -> ByteSize:
    """return the size of regular files under `path` in bytes

    The result is a heuristic used to scale upload delays and must never raise:
    entries can vanish mid-walk and symlink cycles can fail to resolve.
    Symlinks are not followed so cycles cannot cause recursion.

    NOTE: performance of this degrades with large amounts of files
    until we do not hit 1 million it can be ignored
    NOTE: file size has no impact on performance
    """
    total = 0
    dir_paths = [os.fspath(path)]
    while dir_paths:
        dir_path = dir_paths.pop()
        with suppress(OSError), os.scandir(dir_path) as it:
            for entry in it:
                with suppress(OSError):
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        dir_paths.append(entry.path)
    return TypeAdapter(ByteSize).validate_python(total)
