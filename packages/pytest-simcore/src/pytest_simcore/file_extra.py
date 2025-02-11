import logging
from collections.abc import Callable
from pathlib import Path
from typing import Iterable

import pytest
from faker import Faker
from pydantic import ByteSize
from pytest_simcore.helpers.logging_tools import log_context


@pytest.fixture
def random_file_path(tmp_path: Path, faker: Faker) -> Iterable[Path]:
    file = tmp_path / faker.file_name()

    yield file

    if file.exists():
        file.unlink()
    assert not file.exists()


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
    tmp_path: Path, faker: Faker
) -> Callable[[ByteSize, ByteSize, ByteSize], Path]:
    def _create_folder_of_size_with_multiple_files(
        directory_size: ByteSize,
        file_min_size: ByteSize,
        file_max_size: ByteSize,
    ) -> Path:
        # Helper function to create random files and directories
        assert file_min_size > 0
        assert file_min_size <= file_max_size

        def create_random_content(base_dir: Path, remaining_size: ByteSize) -> ByteSize:
            if remaining_size <= 0:
                return remaining_size

            # Decide to create a file or a subdirectory
            # Create a file
            file_size = ByteSize(
                faker.pyint(
                    min_value=min(file_min_size, remaining_size),
                    max_value=min(remaining_size, file_max_size),
                )
            )  # max file size 1MB
            file_path = base_dir / f"{faker.file_path(depth=4, absolute=False)}"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            assert not file_path.exists()
            with file_path.open("wb") as fp:
                fp.write(f"I am a {file_size.human_readable()} file".encode())
                fp.truncate(file_size)
            assert file_path.exists()

            return ByteSize(remaining_size - file_size)

        # Recursively create content in the temporary directory
        remaining_size = directory_size
        with log_context(
            logging.INFO,
            msg=f"creating {directory_size.human_readable()} of random files "
            f"(up to {file_max_size.human_readable()}) in {tmp_path}",
        ) as ctx:
            num_files_created = 0
            while remaining_size > 0:
                remaining_size = create_random_content(tmp_path, remaining_size)
                num_files_created += 1
            ctx.logger.info("created %s files", num_files_created)
        return tmp_path

    return _create_folder_of_size_with_multiple_files
