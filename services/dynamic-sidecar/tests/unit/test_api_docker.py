# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from async_asgi_testclient import TestClient
from fastapi import status
from simcore_service_dynamic_sidecar._meta import API_VTAG


@pytest.fixture
def test_client(test_client: TestClient) -> TestClient:
    return test_client


async def test_are_quotas_supported(
    mock_docker_volume: None, test_client: TestClient, volume_has_quota_support: bool
):
    response = await test_client.post(f"/{API_VTAG}/docker/quotas")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"are_quotas_supported": volume_has_quota_support}
