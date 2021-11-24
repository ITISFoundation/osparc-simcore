# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import filecmp
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

import np_helpers
import pytest
from simcore_sdk.node_ports_common import exceptions, filemanager

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = ["minio", "adminer"]


async def test_valid_upload_download(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: int,
    create_valid_file_uuid: Callable[[Path], str],
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid(file_path)
    store_id, e_tag = await filemanager.upload_file(
        user_id=user_id,
        store_id=s3_simcore_location,
        s3_object=file_id,
        local_file_path=file_path,
    )
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
        s3_object=file_id,
        local_folder=download_folder,
    )
    assert download_file_path.exists()
    assert download_file_path.name == "test.test"
    assert filecmp.cmp(download_file_path, file_path)


async def test_invalid_file_path(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: int,
    create_valid_file_uuid: Callable[[Path], str],
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid(file_path)
    store = s3_simcore_location
    with pytest.raises(FileNotFoundError):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=store,
            s3_object=file_id,
            local_file_path=Path(tmpdir) / "some other file.txt",
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.InvalidDownloadLinkError):
        await filemanager.download_file_from_s3(
            user_id=user_id,
            store_id=store,
            s3_object=file_id,
            local_folder=download_folder,
        )


async def test_errors_upon_invalid_file_identifiers(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: int,
    project_id: str,
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    store = s3_simcore_location
    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.upload_file(
            user_id=user_id, store_id=store, s3_object="", local_file_path=file_path
        )

    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.upload_file(
            user_id=user_id,
            store_id=store,
            s3_object="file_id",
            local_file_path=file_path,
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.download_file_from_s3(
            user_id=user_id, store_id=store, s3_object="", local_folder=download_folder
        )

    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.download_file_from_s3(
            user_id=user_id,
            store_id=store,
            s3_object=np_helpers.file_uuid(
                Path("invisible.txt"), project_id, f"{uuid4()}"
            ),
            local_folder=download_folder,
        )


async def test_invalid_store(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: int,
    create_valid_file_uuid: Callable[[Path], str],
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid(file_path)
    store = "somefunkystore"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.upload_file(
            user_id=user_id,
            store_name=store,
            s3_object=file_id,
            local_file_path=file_path,
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.download_file_from_s3(
            user_id=user_id,
            store_name=store,
            s3_object=file_id,
            local_folder=download_folder,
        )


async def test_valid_metadata(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: int,
    create_valid_file_uuid: Callable[[Path], str],
    s3_simcore_location: str,
):
    # first we go with a non-existing file
    file_path = Path(tmpdir) / "test.test"
    file_id = create_valid_file_uuid(file_path)
    assert file_path.exists() is False

    is_metadata_present = await filemanager.entry_exists(
        user_id=user_id, store_id=s3_simcore_location, s3_object=file_id  # type: ignore
    )
    assert is_metadata_present == False

    # now really create the file and upload it
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid(file_path)
    store_id, e_tag = await filemanager.upload_file(
        user_id=user_id,
        store_id=s3_simcore_location,
        s3_object=file_id,
        local_file_path=file_path,
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
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: int,
    create_valid_file_uuid: Callable[[Path], str],
    s3_simcore_location: str,
    fct: Callable[[int, str, str, Optional[Any]], Awaitable],
):
    file_path = Path(tmpdir) / "test.test"
    file_id = create_valid_file_uuid(file_path)
    assert file_path.exists() is False

    with pytest.raises(exceptions.StorageInvalidCall):
        await fct(
            user_id=None, store_id=s3_simcore_location, s3_object=file_id  # type: ignore
        )
    with pytest.raises(exceptions.StorageInvalidCall):
        await fct(user_id=user_id, store_id=None, s3_object=file_id)  # type: ignore
    with pytest.raises(exceptions.StorageInvalidCall):
        await fct(
            user_id=user_id, store_id=s3_simcore_location, s3_object=None  # type: ignore
        )


async def test_delete_File(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: int,
    create_valid_file_uuid: Callable[[Path], str],
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = create_valid_file_uuid(file_path)
    store_id, e_tag = await filemanager.upload_file(
        user_id=user_id,
        store_id=s3_simcore_location,
        s3_object=file_id,
        local_file_path=file_path,
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
