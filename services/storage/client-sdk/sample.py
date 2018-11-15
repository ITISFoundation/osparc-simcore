""" Example of how to use the client-sdk of simcore-service-storage

    pip install -v  git+https://github.com/itisfoundation/osparc-simcore.git@master#subdirectory=services/storage/client-sdk/python
"""
import asyncio
import filecmp
import tempfile
import urllib
import uuid
from contextlib import contextmanager
from pathlib import Path

from simcore_service_storage_sdk import ApiClient, Configuration, UsersApi
from simcore_service_storage_sdk.rest import ApiException

temporary_file = tempfile.NamedTemporaryFile(delete=False)
temporary_file.close()

temp_file_path = Path(temporary_file.name)
temp_file_path.write_text("Hey Klingons, greetings from down here...")

user_id = "test"
location_name = "simcore.s3"
location_id = 0
bucket_name = "testbucket"
project_id = uuid.uuid4()
node_id = uuid.uuid4()
file_id = temp_file_path.name
file_uuid = "{bucket_name}/{project_id}/{node_id}/{file_id}".format(bucket_name=bucket_name, project_id=project_id, node_id=node_id, file_id=file_id)

@contextmanager
def api_client(cfg):
    client = ApiClient(cfg)
    try:
        yield client
    except ApiException as err:
        print("%s\n" % err)
    finally:
        #NOTE: enforces to closing client session and connector.
        # this is a defect of the sdk
        del client.rest_client

async def test_health_check(api:UsersApi):
    res = await api.health_check()
    print("health check:", res)
    assert not res.error
    assert res.data

async def test_get_locations(api:UsersApi):
    res = await api.get_storage_locations(user_id=user_id)
    print("get locations:", res)
    assert not res.error
    assert res.data

async def test_upload_file(api:UsersApi):
    res = await api.upload_file(location_id=location_id, user_id=user_id, file_id=file_uuid)
    print("upload files:", res)
    assert not res.error
    assert res.data
    assert res.data.link
    upload_link = res.data.link
    # upload file using link
    with Path(temporary_file.name).open('rb') as fp:
        d = fp.read()
        req = urllib.request.Request(upload_link, data=d, method='PUT')
        with urllib.request.urlopen(req) as _f:
            pass

async def test_download_file(api:UsersApi):
    res = await api.download_file(location_id=location_id, user_id=user_id, file_id=file_uuid)
    print("download file:", res)
    assert not res.error
    assert res.data
    assert res.data.link
    download_link = res.data.link
    # upload file using link
    tmp_file2 = tempfile.NamedTemporaryFile(delete=False)
    tmp_file2.close()
    urllib.request.urlretrieve(download_link, tmp_file2.name)

    assert filecmp.cmp(tmp_file2.name, temp_file_path)

async def test_delete_file(api:UsersApi):
    res = await api.delete_file(location_id=location_id, user_id=user_id, file_id=file_uuid)
    print("delete file:", res)
    assert not res

async def test_get_files_metada(api:UsersApi):
    res = await api.get_files_metadata(location_id=location_id, user_id=user_id)
    print("get files metadata:", res)
    assert not res.error
    assert res.data

async def test_get_file_metada(api:UsersApi):
    res = await api.get_file_metadata(user_id=user_id, location_id=location_id, file_id=file_uuid)
    print("get file metadata", res)
    assert not res.error
    assert res.data


async def run_test():
    cfg = Configuration()
    cfg.host = cfg.host.format(
        host="localhost",
        port=11111,
        basePath="v0"
    )

    with api_client(cfg) as client:
        api = UsersApi(client)

        await test_health_check(api)
        await test_get_locations(api)
        await test_upload_file(api)
        await test_get_files_metada(api)
        await test_get_file_metada(api)
        await test_download_file(api)
        await test_delete_file(api)




def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_test())

if __name__ == "__main__":
    main()
