# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from aiohttp.test_utils import TestClient
from simcore_service_storage.s3 import get_s3_client
from simcore_service_storage.settings import Settings

pytest_simcore_core_services_selection = ["postgres"]


async def test_s3_client(app_settings: Settings, client: TestClient):
    assert client.app
    assert app_settings.STORAGE_S3
    s3_client = get_s3_client(client.app)
    assert s3_client

    response = await s3_client.client.list_buckets()
    assert response
    assert "Buckets" in response
    assert len(response["Buckets"]) == 1
    assert "Name" in response["Buckets"][0]
    assert response["Buckets"][0]["Name"] == app_settings.STORAGE_S3.S3_BUCKET_NAME
