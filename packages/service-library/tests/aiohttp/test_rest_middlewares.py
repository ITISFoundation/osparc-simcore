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
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_middlewares import (
    envelope_middleware_factory,
    error_middleware_factory,
)
from servicelib.aiohttp.rest_responses import is_enveloped, unwrap_envelope
from servicelib.aiohttp.web_exceptions_extension import get_http_error_class_or_none
from servicelib.json_serialization import json_dumps
from servicelib.status_codes_utils import get_http_status_codes, is_server_error


@dataclass
class Data:
    x: int = 3
    y: str = "foo"


class SomeUnhandledError(Exception):
    ...


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
    async def get_obj(request: web.Request):
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
    def returns_value(cls, suffix):
        handlers = cls()
        coro = getattr(handlers, "get_" + suffix)
        loop = asyncio.get_event_loop()
        returned_value = loop.run_until_complete(coro(None))
        return json.loads(json_dumps(returned_value))

    FAIL_REASON = "Failed with  {}"

    @classmethod
    async def fail(cls, request: web.Request):
        status_code = int(request.query["code"])
        http_error_cls = get_http_error_class_or_none(status_code)
        assert http_error_cls
        raise http_error_cls(reason=cls.FAIL_REASON.format(status_code))

    FAIL_UNEXPECTED_REASON = "Unexpected error"

    @classmethod
    async def fail_unexpected(cls, request: web.Request):
        raise SomeUnhandledError(cls.FAIL_UNEXPECTED_REASON)


@pytest.fixture
def client(event_loop, aiohttp_client):
    app = web.Application()

    # routes
    app.router.add_routes(
        [
            web.get(path, handler, name=handler.__name__)
            for path, handler in [
                ("/v1/health", Handlers.get_health),
                ("/v1/dict", Handlers.get_dict),
                ("/v1/envelope", Handlers.get_envelope),
                ("/v1/list", Handlers.get_list),
                ("/v1/obj", Handlers.get_obj),
                ("/v1/string", Handlers.get_string),
                ("/v1/number", Handlers.get_number),
                ("/v1/mixed", Handlers.get_mixed),
                ("/v1/fail", Handlers.fail),
                ("/v1/fail_unexpected", Handlers.fail_unexpected),
            ]
        ]
    )

    # middlewares
    app.middlewares.append(error_middleware_factory(api_version="/v1"))
    app.middlewares.append(envelope_middleware_factory(api_version="/v1"))

    return event_loop.run_until_complete(aiohttp_client(app))


@pytest.mark.parametrize(
    "path,expected_data",
    [
        ("/health", Handlers.returns_value("health")),
        ("/dict", Handlers.returns_value("dict")),
        ("/envelope", Handlers.returns_value("envelope")["data"]),
        ("/list", Handlers.returns_value("list")),
        ("/obj", Handlers.returns_value("obj")),
        ("/string", Handlers.returns_value("string")),
        ("/number", Handlers.returns_value("number")),
        ("/mixed", Handlers.returns_value("mixed")),
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
    assert response.status == status.HTTP_404_NOT_FOUND, payload

    response = await client.get("/v1/some-invalid-address-in-api")
    payload = await response.json()
    assert response.status == status.HTTP_404_NOT_FOUND, payload

    assert is_enveloped(payload)

    data, error = unwrap_envelope(payload)
    assert error
    assert not data


@pytest.mark.parametrize("status_code", get_http_status_codes(status, is_server_error))
async def test_fails_with_http_server_error(client: TestClient, status_code: int):
    response = await client.get("/v1/fail", params={"code": status_code})
    assert response.status == status_code

    data, error = unwrap_envelope(await response.json())
    assert not data
    assert error
    assert error["message"] == Handlers.FAIL_REASON.format(status_code)


async def test_raised_unhandled_exception(
    client: TestClient, capsys: pytest.CaptureFixture
):
    response = await client.get("/v1/fail_unexpected")
    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # TODO: exception is
    #
    # - Response body conforms OAS schema model

    data, error = unwrap_envelope(await response.json())
    assert not data
    assert error
    assert error["message"] == Handlers.FAIL_UNEXPECTED_REASON
