# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from common_library.json_serialization import json_dumps
from pytest_mock import MockerFixture
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_middlewares import (
    envelope_middleware_factory,
    error_middleware_factory,
)
from servicelib.rest_responses import is_enveloped, unwrap_envelope


@dataclass
class Data:
    x: int = 3
    y: str = "foo"


class SomeUnexpectedError(Exception): ...


class Handlers:
    @staticmethod
    async def get_health_wrong(_request: web.Request):
        return {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "invalid_entry": 125,
        }

    @staticmethod
    async def get_health(_request: web.Request):
        return {
            "name": __name__.split(".")[0],
            "version": "1.0",
            "status": "SERVICE_RUNNING",
            "api_version": "1.0",
        }

    @staticmethod
    async def get_dict(_request: web.Request):
        return {"x": 3, "y": "3"}

    @staticmethod
    async def get_envelope(_request: web.Request):
        data = {"x": 3, "y": "3"}
        return {"error": None, "data": data}

    @staticmethod
    async def get_list(_request: web.Request):
        return [{"x": 3, "y": "3"}] * 3

    @staticmethod
    async def get_obj(_request: web.Request):
        return Data(3, "3")

    @staticmethod
    async def get_string(_request: web.Request):
        return "foo"

    @staticmethod
    async def get_number(_request: web.Request):
        return 3

    @staticmethod
    async def get_mixed(_request: web.Request):
        return [{"x": 3, "y": "3", "z": [Data(3, "3")] * 2}] * 3

    @classmethod
    def returns_value(cls, suffix):
        handlers = cls()
        coro = getattr(handlers, "get_" + suffix)
        loop = asyncio.get_event_loop()
        returned_value = loop.run_until_complete(coro(None))
        return json.loads(json_dumps(returned_value))

    EXPECTED_RAISE_UNEXPECTED_REASON = "Unexpected error"

    @classmethod
    async def raise_exception(cls, request: web.Request):
        exc_name = request.query.get("exc")
        match exc_name:
            case NotImplementedError.__name__:
                raise NotImplementedError
            case asyncio.TimeoutError.__name__:
                raise TimeoutError
            case web.HTTPOk.__name__:
                raise web.HTTPOk  # 2XX
            case web.HTTPUnauthorized.__name__:
                raise web.HTTPUnauthorized  # 4XX
            case web.HTTPServiceUnavailable.__name__:
                raise web.HTTPServiceUnavailable  # 5XX
            case _:  # unexpected
                raise SomeUnexpectedError(cls.EXPECTED_RAISE_UNEXPECTED_REASON)

    @staticmethod
    async def raise_error(_request: web.Request):
        raise web.HTTPNotFound

    @staticmethod
    async def raise_error_with_reason(_request: web.Request):
        raise web.HTTPNotFound(reason="A short phrase")

    @staticmethod
    async def raise_success(_request: web.Request):
        raise web.HTTPOk

    @staticmethod
    async def raise_success_with_reason(_request: web.Request):
        raise web.HTTPOk(reason="I'm ok")

    @staticmethod
    async def raise_success_with_text(_request: web.Request):
        # NOTE: explicitly NOT enveloped!
        raise web.HTTPOk(reason="I'm ok", text=json.dumps({"ok": True}))


@pytest.fixture
async def client(
    aiohttp_client: Callable,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("SC_BUILD_TARGET", "production")

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
                # custom use cases
                ("/v1/raise_exception", Handlers.raise_exception),
                ("/v1/raise_error", Handlers.raise_error),
                ("/v1/raise_error_with_reason", Handlers.raise_error_with_reason),
                ("/v1/raise_success", Handlers.raise_success),
                ("/v1/raise_success_with_reason", Handlers.raise_success_with_reason),
                ("/v1/raise_success_with_text", Handlers.raise_success_with_text),
            ]
        ]
    )

    app.router.add_routes(
        [
            web.get(
                "/free/raise_exception",
                Handlers.raise_exception,
                name="raise_exception_without_middleware",
            )
        ]
    )
    # middlewares
    app.middlewares.append(error_middleware_factory(api_version="/v1"))
    app.middlewares.append(envelope_middleware_factory(api_version="/v1"))

    return await aiohttp_client(app)


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


async def test_404_not_found_when_entrypoint_not_exposed(client: TestClient):
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


async def test_raised_unhandled_exception(
    client: TestClient, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.ERROR):
        response = await client.get("/v1/raise_exception")

        # respond the client with 500
        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR

        # response model
        data, error = unwrap_envelope(await response.json())
        assert not data
        assert error

        # avoids details
        assert not error.get("errors")
        assert not error.get("logs")

        # - log sufficient information to diagnose the issue
        #
        # ERROR    servicelib.aiohttp.rest_middlewares:rest_middlewares.py:75 We apologize ... [OEC:128594540599840].
        # {
        # "exception_details": "Unexpected error",
        # "error_code": "OEC:128594540599840",
        # "context": {
        #     "request.remote": "127.0.0.1",
        #     "request.method": "GET",
        #     "request.path": "/v1/raise_exception"
        # },
        # "tip": null
        # }
        # Traceback (most recent call last):
        # File "/osparc-simcore/packages/service-library/src/servicelib/aiohttp/rest_middlewares.py", line 94, in _middleware_handler
        #     return await handler(request)
        #         ^^^^^^^^^^^^^^^^^^^^^^
        # File "/osparc-simcore/packages/service-library/src/servicelib/aiohttp/rest_middlewares.py", line 186, in _middleware_handler
        #     resp = await handler(request)
        #         ^^^^^^^^^^^^^^^^^^^^^^
        # File "/osparc-simcore/packages/service-library/tests/aiohttp/test_rest_middlewares.py", line 109, in raise_exception
        #     raise SomeUnexpectedError(cls.EXPECTED_RAISE_UNEXPECTED_REASON)
        # tests.aiohttp.test_rest_middlewares.SomeUnexpectedError: Unexpected error

        assert response.method in caplog.text
        assert response.url.path in caplog.text
        assert "exception_details" in caplog.text
        assert "request.remote" in caplog.text
        assert "context" in caplog.text
        assert SomeUnexpectedError.__name__ in caplog.text
        assert Handlers.EXPECTED_RAISE_UNEXPECTED_REASON in caplog.text

        # log OEC
        assert "OEC:" in caplog.text


async def test_not_implemented_error_is_501(client: TestClient):
    """Test that NotImplementedError is correctly mapped to HTTP 501 NOT IMPLEMENTED."""
    response = await client.get(
        "/v1/raise_exception", params={"exc": NotImplementedError.__name__}
    )
    assert response.status == status.HTTP_501_NOT_IMPLEMENTED

    # Check that the response is properly enveloped
    payload = await response.json()
    assert is_enveloped(payload)

    # Verify error details
    data, error = unwrap_envelope(payload)
    assert not data
    assert error
    assert error.get("status") == status.HTTP_501_NOT_IMPLEMENTED


async def test_timeout_error_is_504(client: TestClient):
    """Test that TimeoutError is correctly mapped to HTTP 504 GATEWAY TIMEOUT."""
    response = await client.get(
        "/v1/raise_exception", params={"exc": asyncio.TimeoutError.__name__}
    )
    assert response.status == status.HTTP_504_GATEWAY_TIMEOUT

    # Check that the response is properly enveloped
    payload = await response.json()
    assert is_enveloped(payload)

    # Verify error details
    data, error = unwrap_envelope(payload)
    assert not data
    assert error
    assert error.get("status") == status.HTTP_504_GATEWAY_TIMEOUT


async def test_exception_in_non_api_route(client: TestClient):
    """Test how exceptions are handled in routes not under the API path."""
    response = await client.get("/free/raise_exception")

    # This should be a raw exception, not processed by our middleware
    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Should not be enveloped since it's outside the API path
    text = await response.text()
    try:
        # If it happens to be JSON, check it's not enveloped
        payload = json.loads(text)
        assert not is_enveloped(payload)
    except json.JSONDecodeError:
        # If it's not JSON, that's expected too
        pass


async def test_http_ok_with_text_is_enveloped(client: TestClient):
    """Test that HTTPOk with text is properly enveloped."""
    response = await client.get("/v1/raise_success_with_text")
    assert response.status == status.HTTP_200_OK

    # Should be enveloped
    payload = await response.json()
    assert is_enveloped(payload)

    # Check the content was preserved
    data, error = unwrap_envelope(payload)
    assert not error
    assert data
    assert data.get("ok") is True


async def test_exception_in_handler_returns_500(
    client: TestClient, mocker: MockerFixture
):
    """Test that exceptions in the handler functions are caught and return 500."""

    # Mock _handle_http_successful to raise an exception
    def mocked_handler(*args, **kwargs):
        msg = "Simulated error in handler"
        raise ValueError(msg)

    mocker.patch(
        "servicelib.aiohttp.rest_middlewares._handle_http_successful",
        side_effect=mocked_handler,
    )

    # Trigger a successful HTTP response that will be processed by our mocked handler
    response = await client.get(
        "/v1/raise_exception", params={"exc": web.HTTPOk.__name__}
    )

    # Should return 500 since our handler raised an exception
    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Check that the response is properly enveloped
    payload = await response.json()
    assert is_enveloped(payload)

    # Verify error details
    data, error = unwrap_envelope(payload)
    assert not data
    assert error
    assert error.get("status") == status.HTTP_500_INTERNAL_SERVER_ERROR

    # Make sure there are no detailed error logs in production mode
    assert not error.get("errors")
    assert not error.get("logs")
