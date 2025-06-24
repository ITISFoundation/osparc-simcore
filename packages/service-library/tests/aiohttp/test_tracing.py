# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import importlib
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pip
import pytest
from aiohttp import web
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import ValidationError
from servicelib.aiohttp.tracing import get_tracing_lifespan
from servicelib.tracing import _OSPARC_TRACE_ID_HEADER
from settings_library.tracing import TracingSettings


@pytest.fixture
def tracing_settings_in(request):
    return request.param


@pytest.fixture()
def set_and_clean_settings_env_vars(
    monkeypatch: pytest.MonkeyPatch, tracing_settings_in
):
    endpoint_mocked = False
    if tracing_settings_in[0]:
        endpoint_mocked = True
        monkeypatch.setenv(
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT", f"{tracing_settings_in[0]}"
        )
    port_mocked = False
    if tracing_settings_in[1]:
        port_mocked = True
        monkeypatch.setenv(
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT", f"{tracing_settings_in[1]}"
        )
    yield
    if endpoint_mocked:
        monkeypatch.delenv("TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT")
    if port_mocked:
        monkeypatch.delenv("TRACING_OPENTELEMETRY_COLLECTOR_PORT")


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318),
    ],
    indirect=True,
)
async def test_valid_tracing_settings(
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in,
    uninstrument_opentelemetry: Iterator[None],
):
    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()
    async for _ in get_tracing_lifespan(
        app=app, service_name=service_name, tracing_settings=tracing_settings
    )(app):
        pass


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
    tracing_settings_in,
    uninstrument_opentelemetry: Iterator[None],
):
    with pytest.raises(ValidationError):
        TracingSettings.create_from_envs()


def install_package(package):
    pip.main(["install", package])


def uninstall_package(package):
    pip.main(["uninstall", "-y", package])


@pytest.fixture
def manage_package(request):
    package, importname = request.param
    install_package(package)
    yield importname
    uninstall_package(package)


@pytest.mark.skip(
    reason="this test installs always the latest version of the package which creates conflicts."
)
@pytest.mark.parametrize(
    "tracing_settings_in, manage_package",
    [
        (
            ("http://opentelemetry-collector", 4318),
            (
                "opentelemetry-instrumentation-botocore",
                "opentelemetry.instrumentation.botocore",
            ),
        ),
        (
            ("http://opentelemetry-collector", "4318"),
            (
                "opentelemetry-instrumentation-aiopg",
                "opentelemetry.instrumentation.aiopg",
            ),
        ),
    ],
    indirect=True,
)
async def test_tracing_setup_package_detection(
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
    manage_package,
    uninstrument_opentelemetry: Iterator[None],
):
    package_name = manage_package
    importlib.import_module(package_name)
    #
    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()
    async for _ in get_tracing_lifespan(
        app=app,
        service_name=service_name,
        tracing_settings=tracing_settings,
    )(app):
        # idempotency
        async for _ in get_tracing_lifespan(
            app=app,
            service_name=service_name,
            tracing_settings=tracing_settings,
        )(app):
            pass


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318),
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "server_response", [web.Response(text="Hello, world!"), web.HTTPNotFound()]
)
async def test_trace_id_in_response_header(
    mock_otel_collector: InMemorySpanExporter,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in,
    uninstrument_opentelemetry: Iterator[None],
    server_response: web.Response | web.HTTPException,
) -> None:
    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()

    async def handler(handler_data: dict, request: web.Request) -> web.Response:
        current_span = trace.get_current_span()
        handler_data[_OSPARC_TRACE_ID_HEADER] = format(
            current_span.get_span_context().trace_id, "032x"
        )
        if isinstance(server_response, web.HTTPException):
            raise server_response
        return server_response

    handler_data = {}
    app.router.add_get("/", partial(handler, handler_data))

    async for _ in get_tracing_lifespan(
        app=app,
        service_name=service_name,
        tracing_settings=tracing_settings,
        add_response_trace_id_header=True,
    )(app):
        client = await aiohttp_client(app)
        response = await client.get("/")
        assert _OSPARC_TRACE_ID_HEADER in response.headers
        trace_id = response.headers[_OSPARC_TRACE_ID_HEADER]
        assert len(trace_id) == 32  # Ensure trace ID is a 32-character hex string
        assert (
            trace_id == handler_data[_OSPARC_TRACE_ID_HEADER]
        )  # Ensure trace IDs match
