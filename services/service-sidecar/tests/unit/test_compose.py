import json

# pylint: disable=redefined-outer-name
from typing import Any, Dict

import pytest
import yaml
from async_asgi_testclient import TestClient
from faker import Faker


@pytest.fixture
def compose_spec() -> Dict[str, Any]:
    return {"version": "3", "services": {"container_1": {}, "container_2": {}}}


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
async def test_store_compose_spec(
    test_client: TestClient, compose_spec: Dict[str, Any]
):
    response = await test_client.post("/compose:store", data=json.dumps(compose_spec))
    assert response.status_code == 204
    assert response.text == ""
