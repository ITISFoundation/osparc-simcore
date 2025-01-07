# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pytest
from faker import Faker
from helpers import print_tree
from PIL import Image
from servicelib.file_utils import remove_directory


def _process_and_save_image(image_path: Path) -> None:
    random_image = np.random.rand(900, 900, 3) * 255  # noqa: NPY002
    im_out = Image.fromarray(random_image.astype("uint8")).convert("RGB")
    im_out.save(image_path)


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

    image_paths: list[Path] = []
    for i in range(2):
        image_dir = base_dir / f"images{i}"
        image_dir.mkdir()
        for n in range(50):
            image_paths.append(image_dir / f"out{n}.jpg")  # noqa: PERF401

    with ProcessPoolExecutor() as executor:
        executor.map(_process_and_save_image, image_paths)

    print("mixed_types_dir ---")
    print_tree(base_dir)

    yield base_dir

    await remove_directory(base_dir)
    assert not base_dir.exists()
