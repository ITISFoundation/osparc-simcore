# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import TestClient
from simcore_service_storage.s3 import get_s3_client
from simcore_service_storage.settings import Settings


@pytest.fixture(params=[True, False])
def enable_s3(request: pytest.FixtureRequest) -> bool:
    return request.param  # type: ignore


@pytest.fixture
def mock_config(
    mocked_s3_server_envs, monkeypatch: pytest.MonkeyPatch, enable_s3: bool
):
    # NOTE: override services/storage/tests/conftest.py::mock_config
    monkeypatch.setenv("STORAGE_POSTGRES", "null")
    if not enable_s3:
        # disable S3
        monkeypatch.setenv("STORAGE_S3", "null")


async def test_s3_client(enable_s3: bool, app_settings: Settings, client: TestClient):
    assert client.app
    if enable_s3:
        assert app_settings.STORAGE_S3
        s3_client = get_s3_client(client.app)
        assert s3_client

        response = await s3_client.client.list_buckets()
        assert response
        assert "Buckets" in response
        assert len(response["Buckets"]) == 1
        assert "Name" in response["Buckets"][0]
        assert response["Buckets"][0]["Name"] == app_settings.STORAGE_S3.S3_BUCKET_NAME
    else:
        assert not app_settings.STORAGE_S3
        with pytest.raises(KeyError):
            get_s3_client(client.app)
