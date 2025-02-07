# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import secrets
from collections.abc import AsyncIterable
from pathlib import Path
from unittest.mock import Mock

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from pytest_simcore.helpers.comparing import (
    assert_same_folder_contents,
    get_files_in_folder,
    get_relative_to,
)
from servicelib.archiving_utils import unarchive_dir
from servicelib.file_utils import remove_directory
from servicelib.progress_bar import ProgressBarData
from servicelib.zip_stream import (
    ArchiveEntries,
    DiskStreamReader,
    DiskStreamWriter,
    get_zip_archive_stream,
)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    assert path.exists()
    assert path.is_dir()
    return path


@pytest.fixture
def local_files_dir(tmp_path: Path) -> Path:
    # Cotent to add to the zip
    return _ensure_dir(tmp_path / "local_files_dir")


@pytest.fixture
def local_archive_path(tmp_path: Path) -> Path:
    # local destination of archive (either form S3 or archived locally)
    return tmp_path / "archive.zip"


@pytest.fixture
def local_unpacked_archive(tmp_path: Path) -> Path:
    # contents of unpacked archive
    return _ensure_dir(tmp_path / "unpacked_archive")


def _rand_range(lower: int, upper: int) -> int:
    return secrets.randbelow(upper) + (upper - lower) + 1


def _generate_files_in_path(faker: Faker, base_dir: Path, *, prefix: str = "") -> None:
    # mixed small text files and binary files
    (base_dir / "empty").mkdir()

    (base_dir / "d1").mkdir()
    for i in range(_rand_range(10, 40)):
        (base_dir / "d1" / f"{prefix}f{i}.txt").write_text(faker.text())
        (base_dir / "d1" / f"{prefix}b{i}.bin").write_bytes(faker.json_bytes())

    (base_dir / "d1" / "sd1").mkdir()
    for i in range(_rand_range(10, 40)):
        (base_dir / "d1" / "sd1" / f"{prefix}f{i}.txt").write_text(faker.text())
        (base_dir / "d1" / "sd1" / f"{prefix}b{i}.bin").write_bytes(faker.json_bytes())

    (base_dir / "fancy-names").mkdir()
    for fancy_name in (
        "i have some spaces in my name",
        "(%$)&%$()",
        " ",
    ):
        (base_dir / "fancy-names" / fancy_name).write_text(faker.text())


@pytest.fixture
async def prepare_content(local_files_dir: Path, faker: Faker) -> AsyncIterable[None]:
    _generate_files_in_path(faker, local_files_dir, prefix="local_")
    yield
    await remove_directory(local_files_dir, only_children=True)


@pytest.fixture
def mocked_progress_bar_cb(mocker: MockerFixture) -> Mock:
    def _progress_cb(*args, **kwargs) -> None:
        print(f"received progress: {args}, {kwargs}")

    return mocker.Mock(side_effect=_progress_cb)


async def test_get_zip_archive_stream(
    mocked_progress_bar_cb: Mock,
    prepare_content: None,
    local_files_dir: Path,
    local_archive_path: Path,
    local_unpacked_archive: Path,
):
    # 1. generate archive form soruces
    archive_files: ArchiveEntries = []
    for file in (x for x in local_files_dir.rglob("*") if x.is_file()):
        archive_name = get_relative_to(local_files_dir, file)

        archive_files.append((archive_name, DiskStreamReader(file).get_stream))

    writer = DiskStreamWriter(local_archive_path)

    async with ProgressBarData(
        num_steps=1,
        progress_report_cb=mocked_progress_bar_cb,
        description="root_bar",
    ) as root:
        await writer.write_stream(
            get_zip_archive_stream(archive_files, progress_bar=root)
        )

    # 2. extract archive using exiting tools
    await unarchive_dir(local_archive_path, local_unpacked_archive)

    # 3. compare files in directories (same paths & sizes)
    await assert_same_folder_contents(
        get_files_in_folder(local_files_dir),
        get_files_in_folder(local_unpacked_archive),
    )
