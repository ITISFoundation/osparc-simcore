# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=protected-access

import filecmp
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

import pytest
from aiohttp import ClientError
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_parametrizations import byte_size_ids
from servicelib.progress_bar import ProgressBarData
from settings_library.r_clone import RCloneSettings
from simcore_sdk.node_ports_common import exceptions, filemanager
from simcore_sdk.node_ports_common.r_clone import RCloneFailedError
from yarl import URL

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = ["minio", "adminer"]


@pytest.fixture(params=[True, False], ids=["with RClone", "without RClone"])
def optional_r_clone(
    r_clone_settings: RCloneSettings, request: pytest.FixtureRequest
) -> Optional[RCloneSettings]:
    return r_clone_settings if request.param else None  # type: ignore


def _file_size(size_str: str, **pytest_params):
    return pytest.param(parse_obj_as(ByteSize, size_str), id=size_str, **pytest_params)


@pytest.mark.parametrize(
    "file_size",
    [
        _file_size("10Mib"),
        _file_size("103Mib"),
        _file_size("1003Mib", marks=pytest.mark.heavy_load),
        _file_size("7Gib", marks=pytest.mark.heavy_load),
    ],
    ids=byte_size_ids,
)
async def test_valid_upload_download(
    node_ports_config: None,
    tmpdir: Path,
    user_id: int,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
    file_size: ByteSize,
    create_file_of_size: Callable[[ByteSize, str], Path],
    optional_r_clone: Optional[RCloneSettings],
    simcore_services_ready: None,
    storage_service: URL,
):
    file_path = create_file_of_size(file_size, "test.test")

    file_id = create_valid_file_uuid("", file_path)
    async with ProgressBarData(steps=2) as progress_bar:
        store_id, e_tag = await filemanager.upload_file(
            user_id=user_id,
            store_id=s3_simcore_location,
            store_name=None,
            s3_object=file_id,
            file_to_upload=file_path,
            r_clone_settings=optional_r_clone,
            io_log_redirect_cb=None,
            progress_bar=progress_bar,
        )
        # pylint: disable=protected-access
        assert progress_bar._continuous_progress_value == pytest.approx(1)
        assert store_id == s3_simcore_location
        assert e_tag
        get_store_id, get_e_tag = await filemanager.get_file_metadata(
            user_id=user_id, store_id=store_id, s3_object=file_id
        )
        assert get_store_id == store_id
        assert get_e_tag == e_tag

        download_folder = Path(tmpdir) / "downloads"
        download_file_path = await filemanager.download_file_from_s3(
            user_id=user_id,
            store_id=s3_simcore_location,
            store_name=None,
            s3_object=file_id,
            local_folder=download_folder,
            io_log_redirect_cb=None,
            progress_bar=progress_bar,
        )
        assert progress_bar._continuous_progress_value == pytest.approx(2)
    assert download_file_path.exists()
    assert download_file_path.name == "test.test"
    assert filecmp.cmp(download_file_path, file_path)


@pytest.mark.parametrize(
    "file_size",
    [
        _file_size("10Mib"),
        _file_size("103Mib"),
    ],
    ids=byte_size_ids,
)
async def test_valid_upload_download_using_file_object(
    node_ports_config: None,
    tmpdir: Path,
    user_id: int,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
    file_size: ByteSize,
    create_file_of_size: Callable[[ByteSize, str], Path],
    optional_r_clone: Optional[RCloneSettings],
):
    file_path = create_file_of_size(file_size, "test.test")

    file_id = create_valid_file_uuid("", file_path)
    with file_path.open("rb") as file_object:
        store_id, e_tag = await filemanager.upload_file(
            user_id=user_id,
            store_id=s3_simcore_location,
            store_name=None,
            s3_object=file_id,
            file_to_upload=filemanager.UploadableFileObject(
                file_object, file_path.name, file_path.stat().st_size
            ),
            r_clone_settings=optional_r_clone,
            io_log_redirect_cb=None,
        )
    assert store_id == s3_simcore_location
    assert e_tag
    get_store_id, get_e_tag = await filemanager.get_file_metadata(
        user_id=user_id, store_id=store_id, s3_object=file_id
    )
    assert get_store_id == store_id
    assert get_e_tag == e_tag

    download_folder = Path(tmpdir) / "downloads"
    async with ProgressBarData(steps=1) as progress_bar:
        download_file_path = await filemanager.download_file_from_s3(
            user_id=user_id,
            store_id=s3_simcore_location,
            store_name=None,
            s3_object=file_id,
            local_folder=download_folder,
            io_log_redirect_cb=None,
            progress_bar=progress_bar,
        )
    assert progress_bar._continuous_progress_value == pytest.approx(1)
    assert download_file_path.exists()
    assert download_file_path.name == "test.test"
    assert filecmp.cmp(download_file_path, file_path)


@pytest.fixture
def mocked_upload_file_raising_exceptions(mocker: MockerFixture):
    mocker.patch(
        "simcore_sdk.node_ports_common.filemanager.r_clone.sync_local_to_s3",
        autospec=True,
        side_effect=RCloneFailedError,
    )
    mocker.patch(
        "simcore_sdk.node_ports_common.file_io_utils._upload_file_part",
        autospec=True,
        side_effect=ClientError,
    )


@pytest.mark.parametrize(
    "file_size",
    [
        _file_size("10Mib"),
    ],
    ids=byte_size_ids,
)
async def test_failed_upload_is_properly_removed_from_storage(
    node_ports_config: None,
    create_file_of_size: Callable[[ByteSize], Path],
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
    optional_r_clone: Optional[RCloneSettings],
    file_size: ByteSize,
    user_id: UserID,
    mocked_upload_file_raising_exceptions: None,
):
    file_path = create_file_of_size(file_size)
    file_id = create_valid_file_uuid("", file_path)
    with pytest.raises(exceptions.S3TransferError):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=s3_simcore_location,
            store_name=None,
            s3_object=file_id,
            file_to_upload=file_path,
            r_clone_settings=optional_r_clone,
            io_log_redirect_cb=None,
        )
    with pytest.raises(exceptions.S3InvalidPathError):
        await filemanager.get_file_metadata(
            user_id=user_id, store_id=s3_simcore_location, s3_object=file_id
        )


@pytest.mark.parametrize(
    "file_size",
    [
        _file_size("10Mib"),
    ],
    ids=byte_size_ids,
)
async def test_failed_upload_after_valid_upload_keeps_last_valid_state(
    node_ports_config: None,
    create_file_of_size: Callable[[ByteSize], Path],
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
    optional_r_clone: Optional[RCloneSettings],
    file_size: ByteSize,
    user_id: UserID,
    mocker: MockerFixture,
):
    # upload a valid file
    file_path = create_file_of_size(file_size)
    file_id = create_valid_file_uuid("", file_path)
    store_id, e_tag = await filemanager.upload_file(
        user_id=user_id,
        store_id=s3_simcore_location,
        store_name=None,
        s3_object=file_id,
        file_to_upload=file_path,
        r_clone_settings=optional_r_clone,
        io_log_redirect_cb=None,
    )
    assert store_id == s3_simcore_location
    assert e_tag
    # check the file is correctly uploaded
    get_store_id, get_e_tag = await filemanager.get_file_metadata(
        user_id=user_id, store_id=store_id, s3_object=file_id
    )
    assert get_store_id == store_id
    assert get_e_tag == e_tag
    # now start an invalid update by generating an exception while uploading the same file
    mocker.patch(
        "simcore_sdk.node_ports_common.filemanager.r_clone.sync_local_to_s3",
        autospec=True,
        side_effect=RCloneFailedError,
    )
    mocker.patch(
        "simcore_sdk.node_ports_common.file_io_utils._upload_file_part",
        autospec=True,
        side_effect=ClientError,
    )
    with pytest.raises(exceptions.S3TransferError):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=s3_simcore_location,
            store_name=None,
            s3_object=file_id,
            file_to_upload=file_path,
            r_clone_settings=optional_r_clone,
            io_log_redirect_cb=None,
        )
    # the file shall be back to its original state
    old_store_id, old_e_tag = await filemanager.get_file_metadata(
        user_id=user_id, store_id=s3_simcore_location, s3_object=file_id
    )
    assert get_store_id == old_store_id
    assert get_e_tag == old_e_tag


async def test_invalid_file_path(
    node_ports_config: None,
    tmpdir: Path,
    user_id: int,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid("", file_path)
    store = s3_simcore_location
    with pytest.raises(FileNotFoundError):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=store,
            store_name=None,
            s3_object=file_id,
            file_to_upload=Path(tmpdir) / "some other file.txt",
            io_log_redirect_cb=None,
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.S3InvalidPathError):
        async with ProgressBarData(steps=1) as progress_bar:
            await filemanager.download_file_from_s3(
                user_id=user_id,
                store_id=store,
                store_name=None,
                s3_object=file_id,
                local_folder=download_folder,
                io_log_redirect_cb=None,
                progress_bar=progress_bar,
            )


async def test_errors_upon_invalid_file_identifiers(
    node_ports_config: None,
    tmpdir: Path,
    user_id: UserID,
    project_id: str,
    s3_simcore_location: LocationID,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    store = s3_simcore_location
    with pytest.raises(exceptions.S3InvalidPathError):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=store,
            store_name=None,
            s3_object="",  # type: ignore
            file_to_upload=file_path,
            io_log_redirect_cb=None,
        )

    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=store,
            store_name=None,
            s3_object="file_id",  # type: ignore
            file_to_upload=file_path,
            io_log_redirect_cb=None,
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.S3InvalidPathError):
        async with ProgressBarData(steps=1) as progress_bar:
            await filemanager.download_file_from_s3(
                user_id=user_id,
                store_id=store,
                store_name=None,
                s3_object="",  # type: ignore
                local_folder=download_folder,
                io_log_redirect_cb=None,
                progress_bar=progress_bar,
            )

    with pytest.raises(exceptions.S3InvalidPathError):
        async with ProgressBarData(steps=1) as progress_bar:
            await filemanager.download_file_from_s3(
                user_id=user_id,
                store_id=store,
                store_name=None,
                s3_object=SimcoreS3FileID(f"{project_id}/{uuid4()}/invisible.txt"),
                local_folder=download_folder,
                io_log_redirect_cb=None,
                progress_bar=progress_bar,
            )


async def test_invalid_store(
    node_ports_config: None,
    tmpdir: Path,
    user_id: int,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid("", file_path)
    store = "somefunkystore"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=None,
            store_name=store,  # type: ignore
            s3_object=file_id,
            file_to_upload=file_path,
            io_log_redirect_cb=None,
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.S3InvalidStore):
        async with ProgressBarData(steps=1) as progress_bar:
            await filemanager.download_file_from_s3(
                user_id=user_id,
                store_id=None,
                store_name=store,  # type: ignore
                s3_object=file_id,
                local_folder=download_folder,
                io_log_redirect_cb=None,
                progress_bar=progress_bar,
            )


async def test_valid_metadata(
    node_ports_config: None,
    tmpdir: Path,
    user_id: int,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
):
    # first we go with a non-existing file
    file_path = Path(tmpdir) / "test.test"
    file_id = create_valid_file_uuid("", file_path)
    assert file_path.exists() is False

    is_metadata_present = await filemanager.entry_exists(
        user_id=user_id, store_id=s3_simcore_location, s3_object=file_id  # type: ignore
    )
    assert is_metadata_present == False

    # now really create the file and upload it
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid("", file_path)
    store_id, e_tag = await filemanager.upload_file(
        user_id=user_id,
        store_id=s3_simcore_location,
        store_name=None,
        s3_object=file_id,
        file_to_upload=file_path,
        io_log_redirect_cb=None,
    )
    assert store_id == s3_simcore_location
    assert e_tag

    is_metadata_present = await filemanager.entry_exists(
        user_id=user_id, store_id=store_id, s3_object=file_id
    )

    assert is_metadata_present is True


@pytest.mark.parametrize(
    "fct",
    [filemanager.entry_exists, filemanager.delete_file, filemanager.get_file_metadata],
)
async def test_invalid_call_raises_exception(
    node_ports_config: None,
    tmpdir: Path,
    user_id: int,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
    fct: Callable[[int, str, str, Optional[Any]], Awaitable],
):
    file_path = Path(tmpdir) / "test.test"
    file_id = create_valid_file_uuid("", file_path)
    assert file_path.exists() is False

    with pytest.raises(exceptions.StorageInvalidCall):
        await fct(
            user_id=None, store_id=s3_simcore_location, s3_object=file_id  # type: ignore
        )
    with pytest.raises(exceptions.StorageInvalidCall):
        await fct(user_id=user_id, store_id=None, s3_object=file_id)  # type: ignore
    with pytest.raises(exceptions.StorageInvalidCall):
        await fct(
            user_id=user_id, store_id=s3_simcore_location, s3_object="bing"  # type: ignore
        )


async def test_delete_File(
    node_ports_config: None,
    tmpdir: Path,
    user_id: int,
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid("", file_path)
    store_id, e_tag = await filemanager.upload_file(
        user_id=user_id,
        store_id=s3_simcore_location,
        store_name=None,
        s3_object=file_id,
        file_to_upload=file_path,
        io_log_redirect_cb=None,
    )
    assert store_id == s3_simcore_location
    assert e_tag

    is_metadata_present = await filemanager.entry_exists(
        user_id=user_id, store_id=store_id, s3_object=file_id
    )
    assert is_metadata_present is True

    await filemanager.delete_file(
        user_id=user_id, store_id=s3_simcore_location, s3_object=file_id
    )

    # check that it disappeared
    assert (
        await filemanager.entry_exists(
            user_id=user_id, store_id=store_id, s3_object=file_id
        )
        == False
    )
