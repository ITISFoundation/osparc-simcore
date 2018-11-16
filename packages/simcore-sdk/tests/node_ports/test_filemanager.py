#pylint: disable=W0613, W0621, too-many-arguments
import filecmp
from pathlib import Path

import pytest

from simcore_sdk.node_ports import exceptions, filemanager


@pytest.mark.asyncio
async def test_valid_upload_download(tmpdir, bucket, storage, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()
    
    file_id = file_uuid(file_path)
    store = s3_simcore_location
    await filemanager.upload_file(store_id=store, s3_object=file_id, local_file_path=file_path)

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    await filemanager.download_file(store_id=store, s3_object=file_id, local_file_path=download_file_path)
    assert download_file_path.exists()

    assert filecmp.cmp(download_file_path, file_path)
    
@pytest.mark.asyncio
async def test_invalid_file_path(tmpdir, bucket, storage, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()
    
    
    file_id = file_uuid(file_path)
    store = s3_simcore_location
    with pytest.raises(FileNotFoundError):
        await filemanager.upload_file(store_id=store, s3_object=file_id, local_file_path=Path(tmpdir)/"some other file.txt")

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    with pytest.raises(exceptions.S3InvalidPathError):
        await filemanager.download_file(store_id=store, s3_object=file_id, local_file_path=download_file_path)

@pytest.mark.asyncio
async def test_invalid_fileid(tmpdir, bucket, storage, filemanager_cfg, user_id, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()
    
    store = s3_simcore_location
    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.upload_file(store_id=store, s3_object="", local_file_path=file_path)
    with pytest.raises(exceptions.StorageServerIssue):
        await filemanager.upload_file(store_id=store, s3_object="file_id", local_file_path=file_path)

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    with pytest.raises(exceptions.StorageInvalidCall):
        await filemanager.download_file(store_id=store, s3_object="", local_file_path=download_file_path)
    with pytest.raises(exceptions.S3InvalidPathError):
        await filemanager.download_file(store_id=store, s3_object="file_id", local_file_path=download_file_path)
    
@pytest.mark.asyncio
async def test_invalid_store(tmpdir, bucket, storage, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = file_uuid(file_path)
    store = "somefunkystore"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.upload_file(store_name=store, s3_object=file_id, local_file_path=file_path)

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.download_file(store_name=store, s3_object=file_id, local_file_path=download_file_path)

@pytest.mark.asyncio
async def test_storage_sdk_client(storage):
    pass