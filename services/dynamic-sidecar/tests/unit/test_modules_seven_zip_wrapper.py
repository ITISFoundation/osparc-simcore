# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import subprocess
from pathlib import Path

import pytest
from _pytest._py.path import LocalPath
from faker import Faker
from models_library.basic_types import IDStr
from models_library.progress_bar import ProgressReport
from servicelib.archiving_utils import archive_dir, unarchive_dir
from servicelib.progress_bar import ProgressBarData
from simcore_service_dynamic_sidecar.modules.seven_zip_wrapper import (
    SevenZipError,
    unarchive_zip_to,
)


def _ensure_path(dir_path: Path) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _assert_same_directory_content(path1: Path, path2: Path) -> None:
    assert path1.is_dir()
    assert path2.is_dir()

    contents1 = {p.relative_to(path1) for p in path1.rglob("*")}
    contents2 = {p.relative_to(path2) for p in path2.rglob("*")}

    assert contents1 == contents2


@pytest.fixture
def to_archive_dir(tmpdir: LocalPath) -> Path:
    return _ensure_path(Path(tmpdir) / "to_archive")


@pytest.fixture
def internal_tools_unarchived_tools(tmpdir: LocalPath) -> Path:
    return _ensure_path(Path(tmpdir) / "internal_unarchived")


@pytest.fixture
def external_unarchived_tools(tmpdir: LocalPath) -> Path:
    return _ensure_path(Path(tmpdir) / "external_unarchived")


@pytest.fixture
def archive_path(tmpdir: LocalPath) -> Path:
    return Path(tmpdir) / "archive.zip"


@pytest.fixture
def generate_content(
    to_archive_dir: Path, sub_dirs: int, files_in_subdirs: int
) -> None:
    for i in range(sub_dirs):
        (to_archive_dir / f"s{i}").mkdir(parents=True, exist_ok=True)
        for k in range(files_in_subdirs):
            (to_archive_dir / f"s{i}" / f"{k}.txt").write_text("a" * k)


@pytest.fixture
def skip_if_seven_zip_is_missing() -> None:
    try:
        subprocess.check_output(["7z", "--help"])  # noqa: S607, S603
    except Exception:  # pylint: disable=broad-except
        pytest.skip("7z is not installed")


async def test_missing_path_raises_error(
    skip_if_seven_zip_is_missing: None,
    faker: Faker,
    external_unarchived_tools: Path,
):
    missing_path = Path("/tmp") / f"this_path_is_missing_{faker.uuid4()}"  # noqa: S108
    with pytest.raises(SevenZipError):
        await unarchive_zip_to(missing_path, external_unarchived_tools)


def _print_sorted(unarchived_dir: set[Path]) -> None:
    print(f"List '{unarchived_dir}'")
    for entry in sorted(unarchived_dir):
        print(f"{entry}")


def _strip_folder_from_path(paths: set[Path], *, to_strip: Path) -> set[Path]:
    return {x.relative_to(to_strip) for x in paths}


@pytest.mark.parametrize(
    "sub_dirs, files_in_subdirs",
    [
        pytest.param(50, 40, id="few_items"),
    ],
)
async def test_ensure_same_interface_as_unarchive_dir(
    skip_if_seven_zip_is_missing: None,
    generate_content: Path,
    archive_path: Path,
    to_archive_dir: Path,
    internal_tools_unarchived_tools: Path,
    external_unarchived_tools: Path,
    sub_dirs: int,
    files_in_subdirs: int,
):

    await archive_dir(
        to_archive_dir, archive_path, compress=False, store_relative_path=True
    )

    intenal_response = await unarchive_dir(
        archive_path, internal_tools_unarchived_tools
    )

    last_actual_progress_value = 0

    async def _report_progress(progress_report: ProgressReport) -> None:
        nonlocal last_actual_progress_value
        last_actual_progress_value = progress_report.actual_value

    progress_bar = ProgressBarData(
        num_steps=1,
        description=IDStr("test progress bar"),
        progress_report_cb=_report_progress,
    )
    async with progress_bar:
        external_response = await unarchive_zip_to(
            archive_path, external_unarchived_tools, progress_bar
        )
    assert last_actual_progress_value == 1  # ensure progress was reported
    assert len(external_response) == sub_dirs * files_in_subdirs

    _assert_same_directory_content(
        internal_tools_unarchived_tools, external_unarchived_tools
    )

    _print_sorted(intenal_response)
    _print_sorted(external_response)

    assert _strip_folder_from_path(
        intenal_response, to_strip=internal_tools_unarchived_tools
    ) == _strip_folder_from_path(external_response, to_strip=external_unarchived_tools)
