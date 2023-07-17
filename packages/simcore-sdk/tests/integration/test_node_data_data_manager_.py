# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import hashlib
import shutil
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings
from simcore_sdk.node_data import data_manager

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = ["minio", "adminer"]


# UTILS


def _remove_path(path: Path) -> None:
    if path.is_file():
        path.unlink()
        assert path.exists() is False
        path.touch()
        assert path.exists() is True
    else:
        shutil.rmtree(path)
        assert path.exists() is False
        path.mkdir(parents=True, exist_ok=True)
        assert path.exists() is True


def _get_file_hashes_in_path(path_to_hash: Path) -> set[tuple[Path, str]]:
    def _hash_path(path: Path):
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _relative_path(root_path: Path, full_path: Path) -> Path:
        return full_path.relative_to(root_path)

    if path_to_hash.is_file():
        return {(_relative_path(path_to_hash, path_to_hash), _hash_path(path_to_hash))}

    return {
        (_relative_path(path_to_hash, path), _hash_path(path))
        for path in path_to_hash.rglob("*")
    }


def _make_file_with_content(file_path: Path) -> Path:
    content = " ".join(f"{uuid4()}" for x in range(10))
    file_path.write_text(content)
    assert file_path.exists()
    return file_path


def _make_dir_with_files(temp_dir: Path, file_count: int) -> Path:
    assert file_count > 0

    content_dir_path = temp_dir / f"content_dir{uuid4()}"
    content_dir_path.mkdir(parents=True, exist_ok=True)

    for _ in range(file_count):
        _make_file_with_content(file_path=content_dir_path / f"{uuid4()}_test.txt")

    return content_dir_path


@pytest.fixture
def node_uuid() -> str:
    return f"{uuid4()}"


@pytest.fixture
def temp_dir(tmpdir: Path) -> Path:
    return Path(tmpdir)


@pytest.fixture
def random_tmp_dir_generator(temp_dir: Path) -> Callable[[bool], Path]:
    def generator(is_file: bool) -> Path:
        random_dir_path = temp_dir / f"{uuid4()}"
        random_dir_path.mkdir(parents=True, exist_ok=True)
        if is_file:
            file_path = random_dir_path / f"{uuid4()}_test.txt"
            file_path.touch()
            return file_path

        return random_dir_path

    return generator


@pytest.fixture
def file_content_path(temp_dir: Path) -> Path:
    return _make_file_with_content(file_path=temp_dir / f"{uuid4()}_test.txt")


@pytest.fixture
def dir_content_one_file_path(temp_dir: Path) -> Path:
    return _make_dir_with_files(temp_dir, file_count=1)


@pytest.fixture
def dir_content_multiple_files_path(temp_dir: Path) -> Path:
    return _make_dir_with_files(temp_dir, file_count=2)


@pytest.mark.parametrize(
    "content_path",
    [
        # pylint: disable=no-member
        pytest.lazy_fixture("file_content_path"),
        pytest.lazy_fixture("dir_content_one_file_path"),
        pytest.lazy_fixture("dir_content_multiple_files_path"),
    ],
)
async def test_valid_upload_download(
    node_ports_config,
    content_path: Path,
    user_id: int,
    project_id: str,
    node_uuid: str,
    r_clone_settings: RCloneSettings,
):
    async with ProgressBarData(steps=2) as progress_bar:
        await data_manager.push(
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            source_path=content_path,
            io_log_redirect_cb=None,
            progress_bar=progress_bar,
            r_clone_settings=r_clone_settings,
        )
        # pylint: disable=protected-access
        assert progress_bar._continuous_progress_value == pytest.approx(1.0)

        uploaded_hashes = _get_file_hashes_in_path(content_path)

        _remove_path(content_path)

        await data_manager.pull(
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            destination_path=content_path,
            io_log_redirect_cb=None,
            r_clone_settings=None,
            progress_bar=progress_bar,
        )
        assert progress_bar._continuous_progress_value == pytest.approx(2.0)

    downloaded_hashes = _get_file_hashes_in_path(content_path)

    assert uploaded_hashes == downloaded_hashes


@pytest.mark.parametrize(
    "content_path",
    [
        # pylint: disable=no-member
        pytest.lazy_fixture("file_content_path"),
        pytest.lazy_fixture("dir_content_one_file_path"),
        pytest.lazy_fixture("dir_content_multiple_files_path"),
    ],
)
async def test_valid_upload_download_saved_to(
    node_ports_config,
    content_path: Path,
    user_id: int,
    project_id: str,
    node_uuid: str,
    random_tmp_dir_generator: Callable,
    r_clone_settings: RCloneSettings,
):
    async with ProgressBarData(steps=2) as progress_bar:
        await data_manager.push(
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            source_path=content_path,
            io_log_redirect_cb=None,
            progress_bar=progress_bar,
            r_clone_settings=r_clone_settings,
        )
        # pylint: disable=protected-access
        assert progress_bar._continuous_progress_value == pytest.approx(1)

        uploaded_hashes = _get_file_hashes_in_path(content_path)

        _remove_path(content_path)

        new_destination = random_tmp_dir_generator(is_file=content_path.is_file())

        await data_manager.pull(
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            destination_path=content_path,
            save_to=new_destination,
            io_log_redirect_cb=None,
            r_clone_settings=None,
            progress_bar=progress_bar,
        )
        assert progress_bar._continuous_progress_value == pytest.approx(2)

    downloaded_hashes = _get_file_hashes_in_path(new_destination)

    assert uploaded_hashes == downloaded_hashes
