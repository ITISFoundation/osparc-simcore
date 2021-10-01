# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json

import pytest
from async_asgi_testclient import TestClient
from async_asgi_testclient.response import Response

pytestmark = pytest.mark.asyncio


def assert_200_empty(response: Response) -> bool:
    assert response.status_code == 200, response.text
    assert json.loads(response.text) == ""
    return True


@pytest.mark.parametrize(
    "route,method",
    [
        # push api module
        ("/push", "POST"),
        # retrieve api module
        ("/retrieve", "GET"),
        ("/retrieve", "POST"),
        # state api module
        ("/state", "GET"),
        ("/state", "POST"),
    ],
)
async def test_mocked_modules(test_client: TestClient, route: str, method: str) -> None:
    response = await test_client.open(route, method=method)
    assert assert_200_empty(response) is True
