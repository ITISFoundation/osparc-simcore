# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Tests for per-request locale resolution (LocaleMiddleware) and
locale-aware exception handlers in the api-server.
"""

import pytest
from common_library.i18n import DEFAULT_LOCALE
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from simcore_service_api_server._locale_middleware import LocaleMiddleware
from simcore_service_api_server.exceptions.handlers._http_exceptions import (
    http_exception_handler,
)
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app_with_middleware() -> FastAPI:
    """Minimal FastAPI app that registers the LocaleMiddleware and exposes
    a single endpoint that echoes ``request.state.locale`` back to the caller.
    """
    app = FastAPI()
    app.add_middleware(LocaleMiddleware)

    @app.get("/locale-echo")
    async def locale_echo(request: Request) -> JSONResponse:
        return JSONResponse({"locale": request.state.locale})

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app_with_middleware())


# ---------------------------------------------------------------------------
# LocaleMiddleware - locale resolution tests
# ---------------------------------------------------------------------------


def test_locale_middleware_x_app_locale_header(client: TestClient):
    resp = client.get("/locale-echo", headers={"X-App-Locale": "es-ES"})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["locale"] == "es_ES"


def test_locale_middleware_accept_language_header(client: TestClient):
    resp = client.get("/locale-echo", headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["locale"] == "zh_CN"


def test_locale_middleware_x_app_locale_takes_precedence_over_accept_language(
    client: TestClient,
):
    resp = client.get(
        "/locale-echo",
        headers={"X-App-Locale": "es-ES", "Accept-Language": "zh-CN"},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["locale"] == "es_ES"


def test_locale_middleware_defaults_to_en_when_no_header(client: TestClient):
    resp = client.get("/locale-echo")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["locale"] == DEFAULT_LOCALE


def test_locale_middleware_invalid_header_falls_back_to_default(client: TestClient):
    resp = client.get("/locale-echo", headers={"Accept-Language": "!!invalid!!"})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["locale"] == DEFAULT_LOCALE


# ---------------------------------------------------------------------------
# Exception handler - locale-aware translation fallback (no .mo catalog)
# ---------------------------------------------------------------------------


def test_exception_handler_falls_back_when_no_locale_state():
    """When LocaleMiddleware is NOT installed, request.state.locale is absent.
    The handler must not raise and must return the original English message.
    """
    app = FastAPI()

    @app.get("/boom")
    async def boom() -> None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    app.add_exception_handler(HTTPException, http_exception_handler)

    with TestClient(app, raise_server_exceptions=False) as tc:
        resp = tc.get("/boom")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    body = resp.json()
    # The detail must survive (pass-through for unknown locale)
    assert body["errors"][0] == "Not Found"
