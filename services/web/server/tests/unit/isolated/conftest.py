import os
import random
import secrets
import string
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def dir_with_random_content(tmpdir) -> Path:
    def random_string(length: int) -> str:
        return "".join(secrets.choice(string.ascii_letters) for i in range(length))

    def make_files_in_dir(dir_path: Path, file_count: int) -> None:
        for _ in range(file_count):
            (dir_path / f"{random_string(8)}.bin").write_bytes(
                os.urandom(random.randint(1, 10))
            )

    def ensure_dir(path_to_ensure: Path) -> Path:
        path_to_ensure.mkdir(parents=True, exist_ok=True)
        return path_to_ensure

    def make_subdirectory_with_content(subdir_name: Path, max_file_count: int) -> None:
        subdir_name = ensure_dir(subdir_name)
        make_files_in_dir(
            dir_path=subdir_name,
            file_count=random.randint(1, max_file_count),
        )

    def make_subdirectories_with_content(
        subdir_name: Path, max_subdirectories_count: int, max_file_count: int
    ) -> None:
        subdirectories_count = random.randint(1, max_subdirectories_count)
        for _ in range(subdirectories_count):
            make_subdirectory_with_content(
                subdir_name=subdir_name / f"{random_string(4)}",
                max_file_count=max_file_count,
            )

    def get_dirs_and_subdris_in_path(path_to_scan: Path) -> Iterator[Path]:
        return (path for path in path_to_scan.rglob("*") if path.is_dir())

    temp_dir_path = Path(tmpdir)
    data_container = ensure_dir(temp_dir_path / "study_data")

    make_subdirectories_with_content(
        subdir_name=data_container, max_subdirectories_count=5, max_file_count=5
    )
    make_files_in_dir(dir_path=data_container, file_count=5)

    # creates a good amount of files
    for _ in range(4):
        for subdirectory_path in get_dirs_and_subdris_in_path(data_container):
            make_subdirectories_with_content(
                subdir_name=subdirectory_path,
                max_subdirectories_count=3,
                max_file_count=3,
            )

    yield temp_dir_path
