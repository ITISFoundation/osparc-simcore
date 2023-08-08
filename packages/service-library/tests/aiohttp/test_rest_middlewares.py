# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from servicelib.aiohttp.rest_middlewares import (
    envelope_middleware_factory,
    error_middleware_factory,
)
from servicelib.aiohttp.rest_responses import is_enveloped, unwrap_envelope
from servicelib.json_serialization import json_dumps


@dataclass
class Data:
    x: int = 3
    y: str = "foo"


class Handlers:
    @staticmethod
    async def get_health_wrong(request: web.Request):
        return {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "invalid_entry": 125,
        }

    @staticmethod
    async def get_health(request: web.Request):
        return {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "api_version": "1.0",
        }

    @staticmethod
    async def get_dict(request: web.Request):
        return {"x": 3, "y": "3"}

    @staticmethod
    async def get_envelope(request: web.Request):
        data = {"x": 3, "y": "3"}
        return {"error": None, "data": data}

    @staticmethod
    async def get_list(request: web.Request):
        return [{"x": 3, "y": "3"}] * 3

    @staticmethod
    async def get_attobj(request: web.Request):
        return Data(3, "3")

    @staticmethod
    async def get_string(request: web.Request):
        return "foo"

    @staticmethod
    async def get_number(request: web.Request):
        return 3

    @staticmethod
    async def get_mixed(request: web.Request):
        return [{"x": 3, "y": "3", "z": [Data(3, "3")] * 2}] * 3

    @classmethod
    def get(cls, suffix):
        handlers = cls()
        coro = getattr(handlers, "get_" + suffix)
        loop = asyncio.get_event_loop()
        data = loop.run_until_complete(coro(None))

        return json.loads(json_dumps(data))


@pytest.fixture
def client(event_loop, aiohttp_client):
    app = web.Application()

    # routes
    app.router.add_routes(
        [
            web.get("/v1/health", Handlers.get_health, name="get_health"),
            web.get("/v1/dict", Handlers.get_dict, name="get_dict"),
            web.get("/v1/envelope", Handlers.get_envelope, name="get_envelope"),
            web.get("/v1/list", Handlers.get_list, name="get_list"),
            web.get("/v1/attobj", Handlers.get_attobj, name="get_attobj"),
            web.get("/v1/string", Handlers.get_string, name="get_string"),
            web.get("/v1/number", Handlers.get_number, name="get_number"),
            web.get("/v1/mixed", Handlers.get_mixed, name="get_mixed"),
        ]
    )

    # middlewares
    app.middlewares.append(error_middleware_factory(api_version="/v1"))
    app.middlewares.append(envelope_middleware_factory(api_version="/v1"))

    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.mark.parametrize(
    "path,expected_data",
    [
        ("/health", Handlers.get("health")),
        ("/dict", Handlers.get("dict")),
        ("/envelope", Handlers.get("envelope")["data"]),
        ("/list", Handlers.get("list")),
        ("/attobj", Handlers.get("attobj")),
        ("/string", Handlers.get("string")),
        ("/number", Handlers.get("number")),
        ("/mixed", Handlers.get("mixed")),
    ],
)
async def test_envelope_middleware(path: str, expected_data: Any, client: TestClient):
    response = await client.get("/v1" + path)
    payload = await response.json()

    assert is_enveloped(payload)

    data, error = unwrap_envelope(payload)
    assert not error
    assert data == expected_data


async def test_404_not_found(client: TestClient):
    response = await client.get("/some-invalid-address-outside-api")
    payload = await response.text()
    assert response.status == 404, payload

    response = await client.get("/v1/some-invalid-address-in-api")
    payload = await response.json()
    assert response.status == 404, payload

    assert is_enveloped(payload)

    data, error = unwrap_envelope(payload)
    assert error
    assert not data
