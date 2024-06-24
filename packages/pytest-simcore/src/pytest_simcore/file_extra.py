import random
from pathlib import Path
from typing import Callable

import pytest
from faker import Faker
from pydantic import ByteSize


@pytest.fixture
def create_file_of_size(tmp_path: Path, faker: Faker) -> Callable[[ByteSize], Path]:
    # NOTE: cleanup is done by tmp_path fixture
    def _creator(size: ByteSize, name: str | None = None) -> Path:
        file: Path = tmp_path / (name or faker.file_name())
        if not file.parent.exists():
            file.parent.mkdir(parents=True)
        with file.open("wb") as fp:
            fp.write(f"I am a {size.human_readable()} file".encode())
            fp.truncate(size)

        assert file.exists()
        assert file.stat().st_size == size
        return file

    return _creator


@pytest.fixture
def create_folder_of_size_with_multiple_files(
    tmp_path: Path,
) -> Callable[[ByteSize, ByteSize], Path]:
    def _create_folder_of_size_with_multiple_files(
        directory_size: ByteSize, file_max_size: ByteSize
    ) -> Path:
        # Helper function to create random files and directories

        def create_random_content(
            current_dir: Path, remaining_size: ByteSize, path_name_suffix: int
        ) -> ByteSize:
            if remaining_size <= 0:
                return remaining_size

            # Decide to create a file or a subdirectory
            if (
                random.choice([True, False]) or remaining_size < 512
            ):  # 512 bytes threshold for files
                # Create a file
                file_size = random.randint(
                    1, min(remaining_size, file_max_size)
                )  # max file size 1MB
                file_path = current_dir / f"file_{path_name_suffix}.txt"
                with file_path.open(file_path, "wb") as fp:
                    fp.write(f"I am a {file_size.human_readable()} file".encode())
                    fp.truncate(file_size)
                remaining_size -= file_size
            else:
                # Create a subdirectory
                sub_dir_path = current_dir / f"dir_{path_name_suffix}"
                sub_dir_path.mkdir()
                remaining_size = create_random_content(
                    sub_dir_path, remaining_size, path_name_suffix
                )

            path_name_suffix += 1

            return remaining_size

        # Recursively create content in the temporary directory
        remaining_size = directory_size
        path_name_suffix = 1
        while remaining_size > 0:
            remaining_size = create_random_content(
                tmp_path, remaining_size, path_name_suffix
            )

        return tmp_path

    return _create_folder_of_size_with_multiple_files
