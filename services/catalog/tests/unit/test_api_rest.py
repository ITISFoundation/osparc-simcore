# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from unittest.mock import Mock

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture


@pytest.fixture
def mocked_get_rabbitmq_rpc_client(mocker: MockerFixture, is_healthy: bool) -> None:
    mock = Mock()
    mock.healthy = is_healthy
    mocker.patch("simcore_service_catalog.api.rest._health.get_rabbitmq_rpc_client", return_value=mock)


@pytest.mark.parametrize("is_healthy", [True, False])
def test_sync_client(
    mocked_get_rabbitmq_rpc_client: None,
    repository_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    background_task_lifespan_disabled: None,
    director_lifespan_disabled: None,
    client: TestClient,
    is_healthy: bool,
):
    response = client.get("/v0/")
    if is_healthy:
        assert response.status_code == status.HTTP_200_OK
    else:
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    response = client.get("/v0/meta")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize("is_healthy", [True, False])
async def test_async_client(
    mocked_get_rabbitmq_rpc_client: None,
    repository_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    background_task_lifespan_disabled: None,
    director_lifespan_disabled: None,
    aclient: httpx.AsyncClient,
    is_healthy: bool,
):
    response = await aclient.get("/v0/")
    if is_healthy:
        assert response.status_code == status.HTTP_200_OK
    else:
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    response = await aclient.get("/v0/meta")
    assert response.status_code == status.HTTP_200_OK
