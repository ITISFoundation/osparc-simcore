# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from asyncio import AbstractEventLoop
from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from servicelib.aiohttp.tracing import setup_tracing
from settings_library.tracing import TracingSettings


@pytest.fixture
def tracing_settings_in(request):
    return request.param


@pytest.fixture()
def set_and_clean_settings_env_vars(monkeypatch: pytest.MonkeyPatch):
    if tracing_settings_in[0]:
        monkeypatch.setenv(
            "TRACING_OTEL_COLLECTOR_ENDPOINT", f"{tracing_settings_in[0]}"
        )
    if tracing_settings_in[1]:
        monkeypatch.setenv("TRACING_OTEL_COLLECTOR_PORT", f"{tracing_settings_in[1]}")


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318),
    ],
    indirect=True,
)
def test_valid_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in: TracingSettings,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    setup_tracing(
        app,
        service_name=service_name,
        tracing_settings=tracing_settings_in,
    )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 80),
        ("opentelemetry-collector", 4318),
        ("httsdasp://ot@##el-collector", 4318),
    ],
    indirect=True,
)
async def test_invalid_tracing_settings(
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in: TracingSettings,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"

    with pytest.raises((BaseException, TypeError)):  # noqa: PT012
        setup_tracing(
            app,
            service_name=service_name,
            tracing_settings=tracing_settings_in,
        )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("", ""),
        (None, None),
        ("", None),
    ],
    indirect=True,
)
async def test_missing_tracing_settings(
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in: TracingSettings,
    caplog,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    # setup_tracing in this case should no nothing
    setup_tracing(app, service_name=service_name, tracing_settings=tracing_settings_in)


@pytest.mark.parametrize(
    "tracing_settings_in",  # noqa: PT002
    [("http://opentelemetry-collector", None), (None, 4318)],
    indirect=True,
)
async def test_incomplete_tracing_settings(
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in: TracingSettings,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    with pytest.raises(RuntimeError):
        setup_tracing(
            app, service_name=service_name, tracing_settings=tracing_settings_in
        )
