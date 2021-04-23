# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from typing import Any, Dict

import pytest
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import status
from simcore_service_dynamic_sidecar._meta import api_vtag

DEFAULT_COMMAND_TIMEOUT = 10.0

pytestmark = pytest.mark.asyncio


@pytest.fixture
def compose_spec() -> str:
    return json.dumps(
        {
            "version": "3",
            "services": {"nginx": {"image": "busybox"}},
        }
    )


async def test_compose_up(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:

    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=compose_spec,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert json.loads(response.text) is None


async def test_compose_up_spec_not_provided(test_client: TestClient) -> None:
    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert json.loads(response.text) == {"detail": "\nProvided yaml is not valid!"}


async def test_compose_up_spec_invalid(test_client: TestClient) -> None:
    invalid_compose_spec = Faker().text()
    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=invalid_compose_spec,
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert "Provided yaml is not valid!" in response.text
    # 28+ characters means the compos spec is also present in the error message
    assert len(response.text) > 28


async def test_containers_down_after_starting(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    # store spec first
    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=compose_spec,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert json.loads(response.text) is None

    response = await test_client.post(
        f"/{api_vtag}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.text != ""


async def test_containers_down_missing_spec(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    response = await test_client.post(
        f"/{api_vtag}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert json.loads(response.text) == {
        "detail": "No spec for docker-compose down was found"
    }
