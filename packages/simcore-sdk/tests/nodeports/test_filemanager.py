#pylint: disable=W0613, W0621
import pytest
from pathlib import Path
import uuid
import filecmp
from simcore_sdk.nodeports import filemanager, config

@pytest.fixture
def user_id()->str:
    yield "testuser"

@pytest.fixture
def filemanager_cfg(user_id, docker_services):
    config.USER_ID = user_id
    config.STORAGE_HOST = "localhost"
    config.STORAGE_PORT = docker_services.port_for('storage', 8080)
    config.STORAGE_VERSION = "v0"
    yield

@pytest.fixture
def s3_simcore_location() ->str:
    yield "simcore.s3"

@pytest.fixture
def file_uuid(bucket):
    def create(store:str, file_path:Path):        
        project = uuid.uuid4()
        node = uuid.uuid4()
        file_id = "{}/{}/{}/{}/{}".format(store, bucket, project, node, file_path.name)
        return file_id
    yield create


async def test_upload_file_to_simcore_s3(tmpdir, bucket, storage_users_api, filemanager_cfg, user_id, file_uuid, s3_simcore_location):
    file_path = Path(tmpdir) / "test.test"
    file_path.write_text("I am a test file")
    assert file_path.exists()
    
    file_id = file_uuid(s3_simcore_location, file_path)    
    store = s3_simcore_location
    s3_object = await filemanager.upload_file_to_s3(store, file_id, file_path)
    assert s3_object == file_id

    download_file_path = Path(tmpdir) / "somedownloaded file.txdt"
    # resp = await storage_users_api.download_file(location_id=0, file_id=file_id, user_id=user_id)
    retrieved_file = await filemanager.download_file_from_S3(store, file_id, download_file_path)
    assert download_file_path.exists()
    assert retrieved_file.exists()
    assert retrieved_file == download_file_path

    assert filecmp.cmp(download_file_path, file_path)
    