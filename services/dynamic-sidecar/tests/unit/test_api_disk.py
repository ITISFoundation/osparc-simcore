# pylint:disable=unused-argument

from async_asgi_testclient import TestClient
from fastapi import status
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.core.emergency_space import (
    _EMERGENCY_DISK_SPACE_NAME,
)


async def test_emergency_disk_space_freed(
    test_client: TestClient, cleanup_emergency_disk_space: None
):
    assert _EMERGENCY_DISK_SPACE_NAME.exists()
    response = await test_client.post(f"/{API_VTAG}/disk/emergency:free")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert not _EMERGENCY_DISK_SPACE_NAME.exists()
