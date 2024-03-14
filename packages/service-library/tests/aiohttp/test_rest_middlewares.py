# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_middlewares import (
    MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE,
    envelope_middleware_factory,
    error_middleware_factory,
)
from servicelib.aiohttp.rest_responses import is_enveloped, unwrap_envelope
from servicelib.aiohttp.web_exceptions_extension import get_all_aiohttp_http_exceptions
from servicelib.error_codes import parse_error_code
from servicelib.json_serialization import json_dumps
from servicelib.status_codes_utils import (
    get_http_status_codes,
    is_client_error,
    is_server_error,
    is_success,
)


@dataclass
class Data:
    x: int = 3
    y: str = "foo"


class SomeUnexpectedError(Exception):
    ...


all_aiohttp_http_exceptions = get_all_aiohttp_http_exceptions()


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

    HTTP_RESPONSE_REASON = "Response with code={}"

    @classmethod
    async def raise_http_response(cls, request: web.Request):
        status_code = int(request.query["code"])
        http_response_cls = all_aiohttp_http_exceptions[status_code]
        raise http_response_cls(reason=cls.HTTP_RESPONSE_REASON.format(status_code))

    RAISE_UNEXPECTED_REASON = "Unexpected error"

    @classmethod
    async def raise_unexpected(cls, request: web.Request):
        assert request
        raise SomeUnexpectedError(cls.RAISE_UNEXPECTED_REASON)

    @classmethod
    async def raise_exception(cls, request: web.Request):
        for exc_cls in (NotImplementedError, asyncio.TimeoutError):
            if exc_cls.__name__ == request.query["exc"]:
                raise exc_cls


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
                ("/v1/raise_http_code", Handlers.raise_http_response),
                ("/v1/raise_unexpected", Handlers.raise_unexpected),
                ("/v1/raise_exception", Handlers.raise_exception),
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
    response = await client.get("/v1/raise_http_code", params={"code": status_code})
    assert response.status == status_code

    data, error = unwrap_envelope(await response.json())
    assert not data
    assert error
    assert error["message"] == Handlers.HTTP_RESPONSE_REASON.format(status_code)


@pytest.mark.parametrize("status_code", get_http_status_codes(status, is_client_error))
async def test_fails_with_http_client_error(client: TestClient, status_code: int):
    response = await client.get("/v1/raise_http_code", params={"code": status_code})
    assert response.status == status_code

    data, error = unwrap_envelope(await response.json())
    assert not data
    assert error
    assert error["message"] == Handlers.HTTP_RESPONSE_REASON.format(status_code)


@pytest.mark.parametrize("status_code", get_http_status_codes(status, is_success))
async def test_fails_with_http_successful(client: TestClient, status_code: int):
    response = await client.get("/v1/raise_http_code", params={"code": status_code})
    assert response.status == status_code

    data, error = unwrap_envelope(await response.json())
    assert not error
    assert data


@pytest.mark.parametrize(
    "exception_cls,expected_code",
    [
        (NotImplementedError, status.HTTP_501_NOT_IMPLEMENTED),
        (asyncio.TimeoutError, status.HTTP_504_GATEWAY_TIMEOUT),
    ],
)
async def test_raised_exception(
    client: TestClient,
    exception_cls: type[Exception],
    expected_code: int,
    caplog: pytest.LogCaptureFixture,
):
    response = await client.get(
        "/v1/raise_exception", params={"exc": exception_cls.__name__}
    )
    assert response.status == expected_code


async def test_raised_unhandled_exception(
    client: TestClient, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.ERROR)
    response = await client.get("/v1/raise_unexpected")

    # respond the client with 500
    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # response model
    data, error = unwrap_envelope(await response.json())
    assert not data
    assert error
    assert "OEC" in error["message"]

    parsed_oec = parse_error_code(error["message"]).pop()
    assert (
        MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE.format(parsed_oec) == error["message"]
    )

    # Log should look like this
    #
    # ERROR    servicelib.aiohttp.rest_middlewares:rest_middlewares.py:96 Request 'GET /v1/raise_unexpected' raised 'SomeUnhandledError' [OEC:140555466658464]
    #   request.remote='127.0.0.1'
    #   request.headers={b'Host': b'127.0.0.1:33461', b'Accept': b'*/*', b'Accept-Encoding': b'gzip, deflate', b'User-Agent': b'Python/3.10 aiohttp/3.8.6'}
    # Traceback (most recent call last):
    # File "osparc-simcore/packages/service-library/src/servicelib/aiohttp/rest_middlewares.py", line 120, in _middleware_handler
    #     return await handler(request)
    # File "osparc-simcore/packages/service-library/src/servicelib/aiohttp/rest_middlewares.py", line 177, in _middleware_handler
    #     resp_or_data = await handler(request)
    # File "osparc-simcore/packages/service-library/tests/aiohttp/test_rest_middlewares.py", line 107, in raise_unexpected
    #     raise SomeUnhandledError(cls.raise_unexpected_REASON)
    # tests.aiohttp.test_rest_middlewares.SomeUnhandledError: Unexpected error

    # log sufficient information to diagnose the issue
    assert response.method in caplog.text
    assert response.url.path in caplog.text
    assert "request.headers=" in caplog.text
    assert "request.remote=" in caplog.text
    assert SomeUnexpectedError.__name__ in caplog.text
    assert Handlers.RAISE_UNEXPECTED_REASON in caplog.text
    # log OEC
    assert "OEC:" in caplog.text
