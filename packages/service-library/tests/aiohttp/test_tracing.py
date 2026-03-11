# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import importlib
from collections.abc import Callable
from functools import partial
from typing import Any

import pip
import pytest
from aiohttp import web
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import ValidationError
from servicelib.aiohttp.tracing import TRACING_CONFIG_KEY, setup_tracing
from servicelib.tracing import _OSPARC_TRACE_ID_HEADER, TracingConfig
from settings_library.tracing import TracingSettings


@pytest.fixture
def tracing_settings_in(request):
    return request.param


@pytest.fixture()
def set_and_clean_settings_env_vars(monkeypatch: pytest.MonkeyPatch, tracing_settings_in):
    endpoint_mocked = False
    if tracing_settings_in[0]:
        endpoint_mocked = True
        monkeypatch.setenv("TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT", f"{tracing_settings_in[0]}")
    port_mocked = False
    if tracing_settings_in[1]:
        port_mocked = True
        monkeypatch.setenv("TRACING_OPENTELEMETRY_COLLECTOR_PORT", f"{tracing_settings_in[1]}")
    sampling_probability_mocked = False
    if tracing_settings_in[2]:
        sampling_probability_mocked = True
        monkeypatch.setenv("TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY", f"{tracing_settings_in[2]}")
    yield
    if endpoint_mocked:
        monkeypatch.delenv("TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT")
    if port_mocked:
        monkeypatch.delenv("TRACING_OPENTELEMETRY_COLLECTOR_PORT")
    if sampling_probability_mocked:
        monkeypatch.delenv("TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY")


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
async def test_valid_tracing_settings(
    mock_otel_collector: InMemorySpanExporter,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in,
):
    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=service_name)
    async for _ in setup_tracing(app=app, tracing_config=tracing_config)(app):
        pass


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 80, 1.0),
        ("opentelemetry-collector", 4318, 1.0),
        ("httsdasp://of@##el-collector", 4318, 1.0),
    ],
    indirect=True,
)
async def test_invalid_tracing_settings(
    mock_otel_collector: InMemorySpanExporter,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in,
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


@pytest.mark.skip(reason="this test installs always the latest version of the package which creates conflicts.")
@pytest.mark.parametrize(
    "tracing_settings_in, manage_package",
    [
        (
            ("http://opentelemetry-collector", 4318, 1.0),
            (
                "opentelemetry-instrumentation-botocore",
                "opentelemetry.instrumentation.botocore",
            ),
        ),
        (
            ("http://opentelemetry-collector", "4318", 1.0),
            (
                "opentelemetry-instrumentation-aiopg",
                "opentelemetry.instrumentation.aiopg",
            ),
        ),
    ],
    indirect=True,
)
async def test_tracing_setup_package_detection(
    mock_otel_collector: InMemorySpanExporter,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
    manage_package,
):
    package_name = manage_package
    importlib.import_module(package_name)
    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=service_name)
    async for _ in setup_tracing(app=app, tracing_config=tracing_config)(app):
        # idempotency
        async for _ in setup_tracing(app=app, tracing_config=tracing_config)(app):
            pass


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
@pytest.mark.parametrize("server_response", [web.Response(text="Hello, world!"), web.HTTPNotFound()])
async def test_trace_id_in_response_header(
    mock_otel_collector: InMemorySpanExporter,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in,
    server_response: web.Response | web.HTTPException,
) -> None:
    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=service_name)
    app[TRACING_CONFIG_KEY] = tracing_config

    async def handler(handler_data: dict, request: web.Request) -> web.Response:
        current_span = trace.get_current_span()
        handler_data[_OSPARC_TRACE_ID_HEADER] = format(current_span.get_span_context().trace_id, "032x")
        if isinstance(server_response, web.HTTPException):
            raise server_response
        return server_response

    handler_data = {}
    app.router.add_get("/", partial(handler, handler_data))

    async for _ in setup_tracing(
        app=app,
        tracing_config=tracing_config,
        add_response_trace_id_header=True,
    )(app):
        client = await aiohttp_client(app)
        response = await client.get("/")
        assert _OSPARC_TRACE_ID_HEADER in response.headers
        trace_id = response.headers[_OSPARC_TRACE_ID_HEADER]
        assert len(trace_id) == 32  # Ensure trace ID is a 32-character hex string
        assert trace_id == handler_data[_OSPARC_TRACE_ID_HEADER]  # Ensure trace IDs match


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 0.05),
    ],
    indirect=True,
)
async def test_tracing_opentelemetry_sampling_probability_effective(
    mock_otel_collector: InMemorySpanExporter,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in,
):
    """
    This test checks that the TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY setting in TracingSettings
    is effective by sending 1000 requests and verifying that the number of collected traces
    is close to 0.05 * 1000 (with some tolerance).
    """
    n_requests = 1000
    tolerance_probability = 0.5

    app = web.Application()
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=service_name)
    app[TRACING_CONFIG_KEY] = tracing_config

    async def handler(request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/", handler)

    async for _ in setup_tracing(app=app, tracing_config=tracing_config)(app):
        client = await aiohttp_client(app)

        await asyncio.gather(*(client.get("/") for _ in range(n_requests)))
        trace_ids = {
            span.context.trace_id for span in mock_otel_collector.get_finished_spans() if span.context is not None
        }
        n_traces = len(trace_ids)
        expected_num_traces = int(tracing_settings.TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY * n_requests)
        tolerance = int(tolerance_probability * expected_num_traces)
        assert expected_num_traces - tolerance <= n_traces <= expected_num_traces + tolerance, (
            f"Expected roughly {expected_num_traces} distinct trace ids, got {n_traces}"
        )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
async def test_tracing_finds_project_id_and_node_id_if_available(
    mock_otel_collector: InMemorySpanExporter,
    aiohttp_client: Callable,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in,
):
    app = web.Application()

    routes = web.RouteTableDef()

    @routes.get("/")
    async def handler(request: web.Request) -> web.Response:
        return web.Response(text="ok")

    @routes.get("/projects/{project_id}/nodes/{node_id}")
    async def handler_with_project_and_node_id_in_path(request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.add_routes(routes)
    service_name = "simcore_service_webserver"
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=service_name)
    app[TRACING_CONFIG_KEY] = tracing_config

    async for _ in setup_tracing(app=app, tracing_config=tracing_config)(app):
        client = await aiohttp_client(app)

        await client.get("/")
        spans = mock_otel_collector.get_finished_spans()
        assert len(spans) == 2  # there is a server span and a client span

        await client.get("/projects/123/nodes/456")
        spans = mock_otel_collector.get_finished_spans()
        assert len(spans) == 4  # there are now 2 more spans, one for the server and one for the client
        server_span = spans[2]  # the third span is the server span for the second request
        assert server_span.attributes
        assert server_span.attributes.get("project_id") == "123"
        assert server_span.attributes.get("node_id") == "456"
