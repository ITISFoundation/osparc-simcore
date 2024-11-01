# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import hashlib
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest
from faker import Faker
from models_library.basic_types import IDStr
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.progress_bar import ProgressBarData
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.r_clone import RCloneSettings
from simcore_sdk.node_data import data_manager
from simcore_sdk.node_ports_common import filemanager
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


# UTILS


def _empty_path(path: Path) -> None:
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
        with Path.open(path, "rb") as f:
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


def _zip_directory(dir_to_compress: Path, destination: Path) -> None:
    dir_to_compress = Path(dir_to_compress)
    destination = Path(destination)

    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in dir_to_compress.glob("**/*"):
            if file_path.is_file():
                zipf.write(file_path, file_path.relative_to(dir_to_compress))


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
def project_id(project_id: str) -> ProjectID:
    return ProjectID(project_id)


@pytest.fixture
def node_uuid(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


@pytest.fixture(params=["dir_content_one_file_path", "dir_content_multiple_files_path"])
def content_path(request: pytest.FixtureRequest, temp_dir: Path) -> Path:
    match request.param:
        case "dir_content_one_file_path":
            return _make_dir_with_files(temp_dir, file_count=1)
        case "dir_content_multiple_files_path":
            return _make_dir_with_files(temp_dir, file_count=2)
        case _:
            pytest.fail("Undefined content_param")


async def test_valid_upload_download(
    node_ports_config: None,
    content_path: Path,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    r_clone_settings: RCloneSettings,
    aws_s3_cli_settings: AwsS3CliSettings,
    mock_io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
):
    async with ProgressBarData(
        num_steps=2, description=IDStr(faker.pystr())
    ) as progress_bar:
        await data_manager._push_directory(  # noqa: SLF001
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            source_path=content_path,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            progress_bar=progress_bar,
            r_clone_settings=r_clone_settings,
            aws_s3_cli_settings=None,
        )
        assert progress_bar._current_steps == pytest.approx(1.0)  # noqa: SLF001

        uploaded_hashes = _get_file_hashes_in_path(content_path)

        _empty_path(content_path)

        await data_manager._pull_directory(  # noqa: SLF001
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            destination_path=content_path,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            r_clone_settings=r_clone_settings,
            progress_bar=progress_bar,
            aws_s3_cli_settings=None,
        )
        assert progress_bar._current_steps == pytest.approx(2.0)  # noqa: SLF001

    downloaded_hashes = _get_file_hashes_in_path(content_path)

    assert uploaded_hashes == downloaded_hashes


async def test_valid_upload_download_saved_to(
    node_ports_config,
    content_path: Path,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    random_tmp_dir_generator: Callable,
    r_clone_settings: RCloneSettings,
    aws_s3_cli_settings: AwsS3CliSettings,
    mock_io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
):
    async with ProgressBarData(
        num_steps=2, description=IDStr(faker.pystr())
    ) as progress_bar:
        await data_manager._push_directory(  # noqa: SLF001
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            source_path=content_path,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            progress_bar=progress_bar,
            r_clone_settings=r_clone_settings,
            aws_s3_cli_settings=None,
        )
        # pylint: disable=protected-access
        assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001

        uploaded_hashes = _get_file_hashes_in_path(content_path)

        _empty_path(content_path)

        new_destination = random_tmp_dir_generator(is_file=content_path.is_file())

        await data_manager._pull_directory(  # noqa: SLF001
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            destination_path=content_path,
            save_to=new_destination,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            r_clone_settings=r_clone_settings,
            progress_bar=progress_bar,
            aws_s3_cli_settings=None,
        )
        assert progress_bar._current_steps == pytest.approx(2)  # noqa: SLF001

    downloaded_hashes = _get_file_hashes_in_path(new_destination)

    assert uploaded_hashes == downloaded_hashes


async def test_delete_legacy_archive(
    node_ports_config,
    content_path: Path,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    r_clone_settings: RCloneSettings,
    temp_dir: Path,
    faker: Faker,
):
    async with ProgressBarData(
        num_steps=2, description=IDStr(faker.pystr())
    ) as progress_bar:
        # NOTE: legacy archives can no longer be crated
        # generating a "legacy style archive"
        archive_into_dir = temp_dir / f"legacy-archive-dir-{uuid4()}"
        archive_into_dir.mkdir(parents=True, exist_ok=True)
        legacy_archive_name = archive_into_dir / f"{content_path.stem}.zip"
        _zip_directory(dir_to_compress=content_path, destination=legacy_archive_name)

        await filemanager.upload_path(
            user_id=user_id,
            store_id=SIMCORE_LOCATION,
            store_name=None,
            s3_object=TypeAdapter(SimcoreS3FileID).validate_python(
                f"{project_id}/{node_uuid}/{legacy_archive_name.name}"
            ),
            path_to_upload=legacy_archive_name,
            io_log_redirect_cb=None,
            progress_bar=progress_bar,
            r_clone_settings=r_clone_settings,
        )

        # pylint: disable=protected-access
        assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001

        assert (
            await data_manager._state_metadata_entry_exists(  # noqa: SLF001
                user_id=user_id,
                project_id=project_id,
                node_uuid=node_uuid,
                path=content_path,
                is_archive=True,
            )
            is True
        )

        await data_manager._delete_legacy_archive(  # noqa: SLF001
            project_id=project_id,
            node_uuid=node_uuid,
            path=content_path,
        )

        assert (
            await data_manager._state_metadata_entry_exists(  # noqa: SLF001
                user_id=user_id,
                project_id=project_id,
                node_uuid=node_uuid,
                path=content_path,
                is_archive=True,
            )
            is False
        )
