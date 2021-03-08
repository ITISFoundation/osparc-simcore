# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import filecmp
from pathlib import Path

import pytest
from simcore_sdk.node_ports import exceptions, filemanager

core_services = ["postgres", "storage"]

ops_services = ["minio"]


async def test_valid_upload_download(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: str,
    file_uuid: str,
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = file_uuid(file_path)
    store_id, e_tag = await filemanager.upload_file(
        store_id=s3_simcore_location, s3_object=file_id, local_file_path=file_path
    )
    assert store_id == s3_simcore_location
    assert e_tag

    download_folder = Path(tmpdir) / "downloads"
    download_file_path = await filemanager.download_file_from_s3(
        store_id=s3_simcore_location, s3_object=file_id, local_folder=download_folder
    )
    assert download_file_path.exists()
    assert download_file_path.name == "test.test"
    assert filecmp.cmp(download_file_path, file_path)


async def test_invalid_file_path(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: str,
    file_uuid: str,
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = file_uuid(file_path)
    store = s3_simcore_location
    with pytest.raises(FileNotFoundError):
        await filemanager.upload_file(
            store_id=store,
            s3_object=file_id,
            local_file_path=Path(tmpdir) / "some other file.txt",
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.InvalidDownloadLinkError):
        await filemanager.download_file_from_s3(
            store_id=store, s3_object=file_id, local_folder=download_folder
        )


async def test_invalid_fileid(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: str,
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    store = s3_simcore_location
    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.upload_file(
            store_id=store, s3_object="", local_file_path=file_path
        )
    with pytest.raises(exceptions.StorageServerIssue):
        await filemanager.upload_file(
            store_id=store, s3_object="file_id", local_file_path=file_path
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.download_file_from_s3(
            store_id=store, s3_object="", local_folder=download_folder
        )
    with pytest.raises(exceptions.InvalidDownloadLinkError):
        await filemanager.download_file_from_s3(
            store_id=store, s3_object="file_id", local_folder=download_folder
        )


async def test_invalid_store(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: str,
    file_uuid: str,
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = file_uuid(file_path)
    store = "somefunkystore"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.upload_file(
            store_name=store, s3_object=file_id, local_file_path=file_path
        )

    download_folder = Path(tmpdir) / "downloads"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.download_file_from_s3(
            store_name=store, s3_object=file_id, local_folder=download_folder
        )


async def test_valid_metadata(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: str,
    file_uuid: str,
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = file_uuid(file_path)
    store_id, e_tag = await filemanager.upload_file(
        store_id=s3_simcore_location, s3_object=file_id, local_file_path=file_path
    )
    assert store_id == s3_simcore_location
    assert e_tag

    is_metadata_present = await filemanager.entry_exists(
        store_id=store_id, s3_object=file_id
    )

    assert is_metadata_present is True


async def test_invalid_metadata(
    tmpdir: Path,
    bucket: str,
    filemanager_cfg: None,
    user_id: str,
    file_uuid: str,
    s3_simcore_location: str,
):
    file_path = Path(tmpdir) / "test.test"
    file_id = file_uuid(file_path)
    assert file_path.exists() is False

    is_metadata_present = await filemanager.entry_exists(
        store_id=s3_simcore_location, s3_object=file_id
    )

    assert is_metadata_present is False