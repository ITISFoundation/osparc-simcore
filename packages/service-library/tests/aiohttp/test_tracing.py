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
    "otel_collector_endpoint, otel_collector_port",  # noqa: PT002
    [
        ("http://otel-collector", 4318),
    ],
)
def test_valid_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    otel_collector_endpoint: str,
    otel_collector_port: int,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    setup_tracing(
        app,
        service_name=service_name,
        otel_collector_endpoint=otel_collector_endpoint,
        otel_collector_port=otel_collector_port,
    )


@pytest.mark.parametrize(
    "otel_collector_endpoint, otel_collector_port",  # noqa: PT002
    [
        ("http://otel-collector", 80),
        ("otel-collector", 4318),
        ("httsdasp://ot@##el-collector", 4318),
    ],
)
def test_invalid_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    otel_collector_endpoint: str,
    otel_collector_port: int,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    setup_tracing(
        app,
        service_name=service_name,
        otel_collector_endpoint=otel_collector_endpoint,
        otel_collector_port=otel_collector_port,
    )
    # assert idempotency
    setup_tracing(
        app,
        service_name=service_name,
        otel_collector_endpoint=otel_collector_endpoint,
        otel_collector_port=otel_collector_port,
    )


@pytest.mark.parametrize(
    "otel_collector_endpoint, otel_collector_port",  # noqa: PT002
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
    otel_collector_endpoint: str,
    otel_collector_port: int,
    caplog,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    # setup_tracing in this case should no nothing
    setup_tracing(
        app,
        service_name=service_name,
        otel_collector_endpoint=otel_collector_endpoint,
        otel_collector_port=otel_collector_port,
    )


@pytest.mark.parametrize(
    "otel_collector_endpoint, otel_collector_port",  # noqa: PT002
    [("http://otel-collector", None), (None, 4318)],
)
def test_incomplete_tracing_settings(
    event_loop: AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    otel_collector_endpoint: str,
    otel_collector_port: int,
) -> TestClient:
    app = web.Application()
    service_name = "simcore_service_webserver"
    with pytest.raises(RuntimeError):
        setup_tracing(
            app,
            service_name=service_name,
            otel_collector_endpoint=otel_collector_endpoint,
            otel_collector_port=otel_collector_port,
        )
