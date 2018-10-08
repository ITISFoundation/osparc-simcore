import pytest
import utils

import simcore_dsm_sdk
from simcore_dsm_sdk import HealthInfo

def test_table_creation(postgres_service):
    utils.create_tables(url=postgres_service)

async def test_app(test_client):
    last_access = -2
    for _ in range(5):
        res = await test_client.get("/v1/")
        check = await res.json()
        print(check["last_access"])
        assert last_access < check["last_access"]
        last_access = check["last_access"]

#FIXME: still not working because of cookies
async def test_api(test_server):
    cfg = simcore_dsm_sdk.Configuration()
    cfg.host = cfg.host.format(
        host=test_server.host,
        port=test_server.port,
        version="v1"
    )
    with utils.api_client(cfg) as api_client:
        session = api_client.rest_client.pool_manager
        for cookie in session.cookie_jar:
            print(cookie.key)
        api = simcore_dsm_sdk.DefaultApi(api_client)
        check = await api.health_check()
        print(check)

        assert isinstance(check, HealthInfo)
        assert check.last_access == -1
        
        #last_access = 0
        for _ in range(5):
            check = await api.health_check()
            print(check)
            #last_access < check.last_access
            last_access = check.last_access

def test_s3(s3_client):
    bucket_name = "simcore-test"
    assert s3_client.create_bucket(bucket_name)
    assert s3_client.exists_bucket(bucket_name)
    s3_client.remove_bucket(bucket_name, delete_contents=True)
    assert not s3_client.exists_bucket(bucket_name)
