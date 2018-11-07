#pylint: disable=W0613, W0621
import filecmp
from pathlib import Path

import pytest

from simcore_sdk.nodeports import exceptions, filemanager


@pytest.mark.asyncio
async def test_valid_upload_download(tmpdir, bucket, storage, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()
    
    file_id = file_uuid(s3_simcore_location, file_path)    
    store = s3_simcore_location
    s3_object = await filemanager.upload_file_to_s3(store, file_id, file_path)
    assert s3_object == file_id

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    retrieved_file = await filemanager.download_file_from_S3(store, file_id, download_file_path)
    assert download_file_path.exists()
    assert retrieved_file.exists()
    assert retrieved_file == download_file_path

    assert filecmp.cmp(download_file_path, file_path)
    
@pytest.mark.asyncio
async def test_invalid_file_path(tmpdir, bucket, storage, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()
    
    file_id = file_uuid(s3_simcore_location, file_path)    
    store = s3_simcore_location
    with pytest.raises(FileNotFoundError):
        await filemanager.upload_file_to_s3(store, file_id, Path(tmpdir)/"some other file.txt")

    download_file_path = Path(tmpdir) / "somedownloaded-<>\//\ file.txdt"
    with pytest.raises(OSError):
        await filemanager.download_file_from_S3(store, file_id, download_file_path)

@pytest.mark.asyncio
async def test_invalid_fileid(tmpdir, bucket, storage, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()
    
    file_id = "some funky id"
    store = s3_simcore_location
    with pytest.raises(exceptions.StorageServerIssue):
        await filemanager.upload_file_to_s3(store, file_id, file_path)

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    with pytest.raises(exceptions.StorageServerIssue):
        await filemanager.download_file_from_S3(store, file_id, download_file_path)

@pytest.mark.asyncio
async def test_invalid_store(tmpdir, bucket, storage, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()

    file_id = file_uuid(s3_simcore_location, file_path)    
    store = "somefunkystore"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.upload_file_to_s3(store, file_id, file_path)

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    with pytest.raises(exceptions.S3InvalidStore):
        await filemanager.download_file_from_S3(store, file_id, download_file_path)

@pytest.mark.asyncio
async def test_storage_sdk_client(storage):
    pass