# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from typing import Any, Dict

import pytest
from async_asgi_testclient import TestClient
from faker import Faker


@pytest.fixture
def compose_spec() -> str:
    return json.dumps(
        {
            "version": "3",
            "services": {"nginx": {"image": "busybox"}},
        }
    )


@pytest.mark.asyncio
async def test_store_compose_spec(
    test_client: TestClient, compose_spec: Dict[str, Any]
):
    response = await test_client.post("/compose:store", data=compose_spec)
    assert response.status_code == 204, response.text
    assert response.text == ""


@pytest.mark.asyncio
async def test_store_compose_spec_not_provided(test_client: TestClient):
    response = await test_client.post("/compose:store")
    assert response.status_code == 400, response.text
    assert response.text == "\nProvided yaml is not valid!"


@pytest.mark.asyncio
async def test_store_compose_spec_invalid(test_client: TestClient):
    invalid_compose_spec = Faker().text()
    response = await test_client.post("/compose:store", data=invalid_compose_spec)
    assert response.status_code == 400, response.text
    assert response.text.endswith("\nProvided yaml is not valid!")
    # 28+ characters means the compos spec is also present in the error message
    assert len(response.text) > 28


@pytest.mark.asyncio
async def test_preload(test_client: TestClient, compose_spec: Dict[str, Any]):
    query_string = dict(command_timeout=5.0)
    response = await test_client.post(
        "/compose:preload", query_string=query_string, data=compose_spec
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_preload_compose_spec_not_provided(test_client: TestClient):
    query_string = dict(command_timeout=5.0)
    response = await test_client.post("/compose:preload", query_string=query_string)
    assert response.status_code == 400, response.text
    assert response.text == "\nProvided yaml is not valid!"


@pytest.mark.asyncio
async def test_compuse_up(test_client: TestClient, compose_spec: Dict[str, Any]):
    # store spec first
    response = await test_client.post("/compose:store", data=compose_spec)
    assert response.status_code == 204, response.text
    assert response.text == ""

    # pull images for spec
    query_string = dict(command_timeout=10.0)
    response = await test_client.post("/compose", query_string=query_string)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_pull(test_client: TestClient, compose_spec: Dict[str, Any]):
    # store spec first
    response = await test_client.post("/compose:store", data=compose_spec)
    assert response.status_code == 204, response.text
    assert response.text == ""

    # pull images for spec
    query_string = dict(command_timeout=10.0)
    response = await test_client.get("/compose:pull", query_string=query_string)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_pull_missing_spec(test_client: TestClient, compose_spec: Dict[str, Any]):
    query_string = dict(command_timeout=5.0)
    response = await test_client.get("/compose:pull", query_string=query_string)
    assert response.status_code == 400, response.text
    assert response.text == "No started spec to stop was found"


@pytest.mark.asyncio
async def test_compuse_stop_after_running(
    test_client: TestClient, compose_spec: Dict[str, Any]
):
    # store spec first
    response = await test_client.post("/compose:store", data=compose_spec)
    assert response.status_code == 204, response.text
    assert response.text == ""

    # pull images for spec
    query_string = dict(command_timeout=10.0)
    response = await test_client.post("/compose", query_string=query_string)
    assert response.status_code == 200, response.text

    response = await test_client.put("/compose:stop", query_string=query_string)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_compuse_delete_after_stopping(
    test_client: TestClient, compose_spec: Dict[str, Any]
):
    # store spec first
    response = await test_client.post("/compose:store", data=compose_spec)
    assert response.status_code == 204, response.text
    assert response.text == ""

    # pull images for spec
    query_string = dict(command_timeout=10.0)
    response = await test_client.post("/compose", query_string=query_string)
    assert response.status_code == 200, response.text

    response = await test_client.put("/compose:stop", query_string=query_string)
    assert response.status_code == 200, response.text

    response = await test_client.delete("/compose", query_string=query_string)
    assert response.status_code == 200, response.text