# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from collections.abc import AsyncIterable
from pathlib import Path

import numpy
import pytest
from faker import Faker
from PIL import Image
from pydantic import NonNegativeInt
from servicelib.archiving_utils._interface_7zip import (
    DecompressProgressParser,
    archive_dir,
)
from servicelib.file_utils import remove_directory


def _print_tree(path: Path, level=0):
    tab = " " * level
    print(f"{tab}{'+' if path.is_dir() else '-'} {path if level==0 else path.name}")
    for p in path.glob("*"):
        _print_tree(p, level + 1)


@pytest.fixture
async def archive_path(tmp_path: Path) -> Path:
    return tmp_path / "mixed_types_dir.zip"


@pytest.fixture
async def mixed_file_types(tmp_path: Path, faker: Faker) -> AsyncIterable[Path]:
    base_dir = tmp_path / "mixed_types_dir"
    base_dir.mkdir()

    # mixed small text files and binary files
    (base_dir / "empty").mkdir()
    (base_dir / "d1").mkdir()
    (base_dir / "d1" / "f1.txt").write_text(faker.text())
    (base_dir / "d1" / "b2.bin").write_bytes(faker.json_bytes())
    (base_dir / "d1" / "sd1").mkdir()
    (base_dir / "d1" / "sd1" / "f1.txt").write_text(faker.text())
    (base_dir / "d1" / "sd1" / "b2.bin").write_bytes(faker.json_bytes())
    (base_dir / "images").mkdir()

    # images cause issues with zipping, below content produced different
    # hashes for zip files
    for i in range(4):
        image_dir = base_dir / f"images{i}"
        image_dir.mkdir()
        for n in range(50):
            a = numpy.random.rand(1900, 1900, 3) * 255  # noqa: NPY002
            im_out = Image.fromarray(a.astype("uint8")).convert("RGB")
            image_path = image_dir / f"out{n}.jpg"
            im_out.save(image_path)

    print("mixed_types_dir ---")
    _print_tree(base_dir)

    yield base_dir

    await remove_directory(base_dir)
    assert not base_dir.exists()


@pytest.fixture
def compress_stdout(package_tests_dir: Path) -> list[str]:
    path = package_tests_dir / "data" / "archive_utils" / "compress_stdout.json"
    assert path.exists()
    return json.loads(path.read_text())


async def test_decompress_progress_parser(compress_stdout: list[str]):
    detected_entries: list[NonNegativeInt] = []

    async def decompressed_bytes(bytes_decompressed: NonNegativeInt) -> None:
        detected_entries.append(bytes_decompressed)

    parser = DecompressProgressParser(decompressed_bytes)
    for chunk in compress_stdout:
        await parser.parse_chunk(chunk)

    assert sum(detected_entries) == 434869455


async def test_something(mixed_file_types: Path, archive_path: Path):
    await archive_dir(
        mixed_file_types, archive_path, compress=True, store_relative_path=True
    )
