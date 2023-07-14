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
