# pylint:disable=protected-access
# pylint:disable=unused-argument
# ruff: noqa: SLF001

from unittest.mock import AsyncMock

from async_asgi_testclient import TestClient
from fastapi import status
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.core import reserved_space


async def test_reserved_disk_space_freed(
    mock_core_rabbitmq: dict[str, AsyncMock],
    cleanup_reserved_disk_space: None,
    test_client: TestClient,
):
    assert reserved_space._RESERVED_DISK_SPACE_NAME.exists()
    response = await test_client.post(f"/{API_VTAG}/disk/reserved:free")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert not reserved_space._RESERVED_DISK_SPACE_NAME.exists()
