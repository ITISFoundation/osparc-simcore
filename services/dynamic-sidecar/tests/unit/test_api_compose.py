# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from typing import Any, Dict

import pytest
from async_asgi_testclient import TestClient
from faker import Faker
from simcore_service_dynamic_sidecar._meta import api_vtag
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

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
        f"/{api_vtag}/containers:up",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=compose_spec,
    )
    assert response.status_code == HTTP_200_OK, response.text


async def test_compose_up_spec_not_provided(test_client: TestClient) -> None:
    response = await test_client.post(
        f"/{api_vtag}/containers:up",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert json.loads(response.text) == {"detail": "\nProvided yaml is not valid!"}


async def test_compose_up_spec_invalid(test_client: TestClient) -> None:
    invalid_compose_spec = Faker().text()
    response = await test_client.post(
        f"/{api_vtag}/containers:up",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=invalid_compose_spec,
    )
    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert "Provided yaml is not valid!" in response.text
    # 28+ characters means the compos spec is also present in the error message
    assert len(response.text) > 28


async def test_containers_pull(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    # store spec first
    response = await test_client.post(
        f"/{api_vtag}/containers:up",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=compose_spec,
    )
    assert response.status_code == HTTP_200_OK, response.text
    assert response.text != ""

    # pull images for spec
    response = await test_client.get(
        f"/{api_vtag}/containers:pull",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == HTTP_200_OK, response.text
    assert response.text != ""


async def test_containers_pull_missing_spec(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers:pull",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert json.loads(response.text) == {
        "detail": "No spec for docker-compose pull was found"
    }


async def test_containers_down_after_stopping(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    # store spec first
    response = await test_client.post(
        f"/{api_vtag}/containers:up",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=compose_spec,
    )
    assert response.status_code == HTTP_200_OK, response.text
    assert response.text != ""

    response = await test_client.post(
        f"/{api_vtag}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == HTTP_200_OK, response.text
    assert response.text != ""


async def test_containers_down_missing_spec(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    response = await test_client.post(
        f"/{api_vtag}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert json.loads(response.text) == {
        "detail": "No spec for docker-compose down was found"
    }
