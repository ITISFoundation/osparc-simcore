# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import hashlib
import os
from asyncio import BaseEventLoop
from pathlib import Path
from typing import Callable, Set, Tuple
from uuid import uuid4

import pytest
from simcore_sdk.node_data import data_manager

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = ["minio", "adminer"]


# UTILS


def _remove_file_or_folder(file_or_folder: Path) -> None:
    if file_or_folder.is_file():
        file_or_folder.unlink()
        assert file_or_folder.exists() is False
        file_or_folder.touch()
        assert file_or_folder.exists() is True
    else:
        os.system(f"rm -rf {file_or_folder}")
        assert file_or_folder.exists() is False
        file_or_folder.mkdir(parents=True, exist_ok=True)
        assert file_or_folder.exists() is True


def _get_file_hashes_in_path(path_to_hash: Path) -> Set[Tuple[Path, str]]:
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


# FIXTURES


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
    loop: BaseEventLoop,
    filemanager_cfg: None,
    content_path: Path,
    user_id: int,
    project_id: str,
    node_uuid: str,
):
    await data_manager.push(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        file_or_folder=content_path,
    )

    uploaded_hashes = _get_file_hashes_in_path(content_path)

    _remove_file_or_folder(content_path)

    await data_manager.pull(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        file_or_folder=content_path,
    )

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
    loop: BaseEventLoop,
    filemanager_cfg: None,
    content_path: Path,
    user_id: int,
    project_id: str,
    node_uuid: str,
    random_tmp_dir_generator: Callable,
):
    await data_manager.push(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        file_or_folder=content_path,
    )

    uploaded_hashes = _get_file_hashes_in_path(content_path)

    _remove_file_or_folder(content_path)

    new_destination = random_tmp_dir_generator(is_file=content_path.is_file())

    await data_manager.pull(
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        file_or_folder=content_path,
        save_to=new_destination,
    )

    downloaded_hashes = _get_file_hashes_in_path(new_destination)

    assert uploaded_hashes == downloaded_hashes
