# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
# pylint:disable=unused-variable

from collections.abc import Callable, Iterator
from filecmp import cmpfiles
from pathlib import Path
from shutil import copy, make_archive

import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pytest_mock import MockerFixture
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings, S3Provider
from simcore_sdk.node_data import data_manager
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB


@pytest.fixture
def create_files() -> Iterator[Callable[..., list[Path]]]:
    created_files = []

    def _create_files(number: int, folder: Path) -> list[Path]:
        for i in range(number):
            file_path = folder / f"{i}.test"
            file_path.write_text(f"I am test file number {i}")
            assert file_path.exists()
            created_files.append(file_path)
        return created_files

    yield _create_files
    # cleanup
    for file_path in created_files:
        file_path.unlink()


@pytest.fixture
def r_clone_settings(faker: Faker) -> RCloneSettings:
    return RCloneSettings.model_validate(
        {
            "R_CLONE_S3": {
                "S3_ENDPOINT": faker.url(),
                "S3_ACCESS_KEY": faker.pystr(),
                "S3_REGION": faker.pystr(),
                "S3_SECRET_KEY": faker.pystr(),
                "S3_BUCKET_NAME": faker.pystr(),
            },
            "R_CLONE_PROVIDER": S3Provider.MINIO,
        }
    )


@pytest.fixture
def project_id(project_id: str) -> ProjectID:
    return ProjectID(project_id)


@pytest.fixture
def node_uuid(node_uuid: str) -> NodeID:
    return NodeID(node_uuid)


async def test_push_folder(
    user_id: int,
    project_id: ProjectID,
    node_uuid: NodeID,
    mocker: MockerFixture,
    tmpdir: Path,
    create_files: Callable[..., list[Path]],
    r_clone_settings: RCloneSettings,
    mock_io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
):
    # create some files
    assert tmpdir.exists()

    # create a folder to upload
    test_folder = Path(tmpdir) / "test_folder"
    test_folder.mkdir()
    assert test_folder.exists()

    # mocks
    mock_filemanager = mocker.patch(
        "simcore_sdk.node_data.data_manager.filemanager", spec=True
    )
    mock_filemanager.upload_path.return_value = ""

    files_number = 10
    create_files(files_number, test_folder)
    assert len(list(test_folder.glob("**/*"))) == files_number
    for file_path in test_folder.glob("**/*"):
        assert file_path.exists()
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        await data_manager._push_directory(  # noqa: SLF001
            user_id,
            project_id,
            node_uuid,
            test_folder,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            progress_bar=progress_bar,
            r_clone_settings=r_clone_settings,
            aws_s3_cli_settings=None,
        )
    assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001

    mock_filemanager.upload_path.assert_called_once_with(
        r_clone_settings=r_clone_settings,
        io_log_redirect_cb=mock_io_log_redirect_cb,
        path_to_upload=test_folder,
        s3_object=f"{project_id}/{node_uuid}/{test_folder.stem}",
        store_id=SIMCORE_LOCATION,
        store_name=None,
        user_id=user_id,
        progress_bar=progress_bar,
        exclude_patterns=None,
        aws_s3_cli_settings=None,
    )


async def test_push_file(
    user_id: int,
    project_id: ProjectID,
    node_uuid: NodeID,
    mocker,
    tmpdir: Path,
    create_files: Callable[..., list[Path]],
    r_clone_settings: RCloneSettings,
    mock_io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
):
    mock_filemanager = mocker.patch(
        "simcore_sdk.node_data.data_manager.filemanager", spec=True
    )
    mock_filemanager.upload_path.return_value = ""
    mock_temporary_directory = mocker.patch(
        "simcore_sdk.node_data.data_manager.TemporaryDirectory"
    )

    file_path = create_files(1, Path(tmpdir))[0]
    assert file_path.exists()

    # test push file by file
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        await data_manager._push_directory(  # noqa: SLF001
            user_id,
            project_id,
            node_uuid,
            file_path,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            progress_bar=progress_bar,
            r_clone_settings=r_clone_settings,
            aws_s3_cli_settings=None,
        )
    assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001
    mock_temporary_directory.assert_not_called()
    mock_filemanager.upload_path.assert_called_once_with(
        r_clone_settings=r_clone_settings,
        io_log_redirect_cb=mock_io_log_redirect_cb,
        path_to_upload=file_path,
        s3_object=f"{project_id}/{node_uuid}/{file_path.name}",
        store_id=SIMCORE_LOCATION,
        store_name=None,
        user_id=user_id,
        progress_bar=progress_bar,
        exclude_patterns=None,
        aws_s3_cli_settings=None,
    )
    mock_filemanager.reset_mock()


async def test_pull_legacy_archive(
    user_id: int,
    project_id: ProjectID,
    node_uuid: NodeID,
    mocker,
    tmpdir: Path,
    create_files: Callable[..., list[Path]],
    mock_io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
):
    assert tmpdir.exists()
    # create a folder to compress from
    test_control_folder = Path(tmpdir) / "test_control_folder"
    test_control_folder.mkdir()
    assert test_control_folder.exists()
    # create the test folder
    test_folder = Path(tmpdir) / "test_folder"
    test_folder.mkdir()
    assert test_folder.exists()
    # create a folder to compress in
    test_compression_folder = Path(tmpdir) / "test_compression_folder"
    test_compression_folder.mkdir()
    assert test_compression_folder.exists()
    # create the zip file
    files_number = 12
    create_files(files_number, test_control_folder)
    compressed_file_name = test_compression_folder / test_folder.stem
    archive_file = make_archive(
        f"{compressed_file_name}", "zip", root_dir=test_control_folder
    )
    assert Path(archive_file).exists()
    # create mock downloaded folder
    test_download_folder = Path(tmpdir) / "test_download_folder"
    test_download_folder.mkdir()
    assert test_download_folder.exists()
    fake_zipped_folder = test_download_folder / Path(archive_file).name
    copy(archive_file, fake_zipped_folder)

    mock_filemanager = mocker.patch(
        "simcore_sdk.node_data.data_manager.filemanager", spec=True
    )
    mock_filemanager.download_path_from_s3.return_value = fake_zipped_folder
    mock_temporary_directory = mocker.patch(
        "simcore_sdk.node_data.data_manager.TemporaryDirectory"
    )
    mock_temporary_directory.return_value.__enter__.return_value = (
        test_compression_folder
    )

    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        await data_manager._pull_legacy_archive(  # noqa: SLF001
            user_id,
            project_id,
            node_uuid,
            test_folder,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            progress_bar=progress_bar,
        )
    assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001
    mock_temporary_directory.assert_called_once()
    mock_filemanager.download_path_from_s3.assert_called_once_with(
        user_id=user_id,
        local_path=test_compression_folder,
        s3_object=f"{project_id}/{node_uuid}/{test_folder.stem}.zip",
        store_id=SIMCORE_LOCATION,
        store_name=None,
        io_log_redirect_cb=mock_io_log_redirect_cb,
        r_clone_settings=None,
        progress_bar=progress_bar._children[0],  # noqa: SLF001
        aws_s3_cli_settings=None,
    )

    matchs, mismatchs, errors = cmpfiles(
        test_folder,
        test_control_folder,
        [x.name for x in test_control_folder.glob("**/*")],
    )
    assert len(matchs) == files_number
    assert not mismatchs
    assert not errors


async def test_pull_directory(
    user_id: int,
    project_id: ProjectID,
    node_uuid: NodeID,
    mocker,
    tmpdir: Path,
    create_files: Callable[..., list[Path]],
    r_clone_settings: RCloneSettings,
    mock_io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
):
    file_path = create_files(1, Path(tmpdir))[0]
    assert file_path.exists()
    assert file_path.is_file()

    fake_download_folder = Path(tmpdir) / "download_folder"
    fake_download_folder.mkdir()

    mock_filemanager = mocker.patch(
        "simcore_sdk.node_data.data_manager.filemanager", spec=True
    )
    mock_filemanager.download_path_from_s3.return_value = fake_download_folder

    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        await data_manager._pull_directory(  # noqa: SLF001
            user_id,
            project_id,
            node_uuid,
            fake_download_folder,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            r_clone_settings=r_clone_settings,
            progress_bar=progress_bar,
            aws_s3_cli_settings=None,
        )
    assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001
    mock_filemanager.download_path_from_s3.assert_called_once_with(
        local_path=fake_download_folder,
        s3_object=f"{project_id}/{node_uuid}/{fake_download_folder.name}",
        store_id=SIMCORE_LOCATION,
        store_name=None,
        user_id=user_id,
        io_log_redirect_cb=mock_io_log_redirect_cb,
        r_clone_settings=r_clone_settings,
        progress_bar=progress_bar,
        aws_s3_cli_settings=None,
    )
