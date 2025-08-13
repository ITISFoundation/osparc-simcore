# pylint:disable=unused-argument

from unittest.mock import AsyncMock

from async_asgi_testclient import TestClient
from fastapi import status
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.core.reserved_space import (
    _RESERVED_DISK_SPACE_NAME,
)


async def test_reserved_disk_space_freed(
    mock_core_rabbitmq: dict[str, AsyncMock],
    cleanup_reserved_disk_space: None,
    test_client: TestClient,
):
    assert _RESERVED_DISK_SPACE_NAME.exists()
    response = await test_client.post(f"/{API_VTAG}/disk/reserved:free")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert not _RESERVED_DISK_SPACE_NAME.exists()
