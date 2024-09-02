# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from asyncio import AbstractEventLoop
from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from servicelib.aiohttp.tracing import setup_tracing


@pytest.mark.parametrize(
    "opentelemetry_collector_endpoint, opentelemetry_collector_port",  # noqa: PT002
    [
        ("http://opentelemetry-collector", 4318),
    ],
)
def test_valid_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    opentelemetry_collector_endpoint: str,
    opentelemetry_collector_port: int,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    setup_tracing(
        app,
        service_name=service_name,
        opentelemetry_collector_endpoint=opentelemetry_collector_endpoint,
        opentelemetry_collector_port=opentelemetry_collector_port,
    )


@pytest.mark.parametrize(
    "opentelemetry_collector_endpoint, opentelemetry_collector_port",  # noqa: PT002
    [
        ("http://opentelemetry-collector", 80),
        ("opentelemetry-collector", 4318),
        ("httsdasp://ot@##el-collector", 4318),
    ],
)
def test_invalid_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    opentelemetry_collector_endpoint: str,
    opentelemetry_collector_port: int,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    setup_tracing(
        app,
        service_name=service_name,
        opentelemetry_collector_endpoint=opentelemetry_collector_endpoint,
        opentelemetry_collector_port=opentelemetry_collector_port,
    )
    # assert idempotency
    setup_tracing(
        app,
        service_name=service_name,
        opentelemetry_collector_endpoint=opentelemetry_collector_endpoint,
        opentelemetry_collector_port=opentelemetry_collector_port,
    )


@pytest.mark.parametrize(
    "opentelemetry_collector_endpoint, opentelemetry_collector_port",  # noqa: PT002
    [
        ("", ""),
        (None, None),
        ("", None),
    ],
)
def test_missing_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    opentelemetry_collector_endpoint: str,
    opentelemetry_collector_port: int,
    caplog,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    # setup_tracing in this case should no nothing
    setup_tracing(
        app,
        service_name=service_name,
        opentelemetry_collector_endpoint=opentelemetry_collector_endpoint,
        opentelemetry_collector_port=opentelemetry_collector_port,
    )


@pytest.mark.parametrize(
    "opentelemetry_collector_endpoint, opentelemetry_collector_port",  # noqa: PT002
    [("http://opentelemetry-collector", None), (None, 4318)],
)
def test_incomplete_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    opentelemetry_collector_endpoint: str,
    opentelemetry_collector_port: int,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    with pytest.raises(RuntimeError):
        setup_tracing(
            app,
            service_name=service_name,
            opentelemetry_collector_endpoint=opentelemetry_collector_endpoint,
            opentelemetry_collector_port=opentelemetry_collector_port,
        )
