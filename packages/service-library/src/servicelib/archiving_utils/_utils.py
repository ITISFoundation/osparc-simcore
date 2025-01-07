from collections.abc import Iterator
from pathlib import Path


def iter_files_to_compress(dir_path: Path) -> Iterator[Path]:
    # NOTE: make sure to sort paths othrwise between different runs
    # the zip will have a different structure and hash
    for path in sorted(dir_path.rglob("*")):
        if path.is_file():
            yield path
