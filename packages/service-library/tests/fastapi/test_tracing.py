# pylint: disable=all


import importlib
import logging
import random
import string
from collections.abc import Callable
from functools import partial
from typing import Any

import pip
import pytest
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import ValidationError
from servicelib.fastapi.tracing import (
    get_tracing_instrumentation_lifespan,
    initialize_fastapi_app_tracing,
)
from servicelib.logging_utils import setup_loggers
from servicelib.tracing import (
    _OSPARC_TRACE_ID_HEADER,
    _PROFILE_ATTRIBUTE_NAME,
    TracingConfig,
    profiled_span,
)
from settings_library.tracing import TracingSettings


@pytest.fixture
def mocked_app() -> FastAPI:
    return FastAPI(title="opentelemetry example")


@pytest.fixture
def tracing_settings_in(request: pytest.FixtureRequest) -> dict[str, Any]:
    return request.param


@pytest.fixture()
def set_and_clean_settings_env_vars(
    monkeypatch: pytest.MonkeyPatch, tracing_settings_in: Callable[[], dict[str, Any]]
) -> None:
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
    sampling_probability_mocked = False
    if tracing_settings_in[2]:
        sampling_probability_mocked = True
        monkeypatch.setenv(
            "TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY", f"{tracing_settings_in[2]}"
        )
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
        ("http://opentelemetry-collector", "4318", 1.0),
    ],
    indirect=True,
)
async def test_valid_tracing_settings(
    mocked_app: FastAPI,
    mock_otel_collector: InMemorySpanExporter,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
):
    tracing_settings = TracingSettings()
    tracing_config = TracingConfig.create(
        tracing_settings=tracing_settings, service_name="Mock-Openetlemetry-Pytest"
    )
    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        async for _ in get_tracing_instrumentation_lifespan(
            tracing_config=tracing_config,
        )(app=mocked_app):
            pass


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 80, 0.5),
        ("http://opentelemetry-collector", 1238712936, 0.5),
        ("opentelemetry-collector", 4318, 0.5),
        ("httsdasp://ot@##el-collector", 4318, 0.5),
        (" !@#$%^&*()[]{};:,<>?\\|`~+=/'\"", 4318, 0.5),
        # The following exceeds max DNS name length
        (
            "".join(random.choice(string.ascii_letters) for _ in range(300)),
            "1238712936",
            0.5,
        ),  # noqa: S311
    ],
    indirect=True,
)
async def test_invalid_tracing_settings(
    mocked_app: FastAPI,
    mock_otel_collector: InMemorySpanExporter,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
):
    app = mocked_app
    with pytest.raises((BaseException, ValidationError, TypeError)):  # noqa: PT012
        tracing_settings = TracingSettings()
        tracing_config = TracingConfig.create(
            tracing_settings=tracing_settings, service_name="Mock-Openetlemetry-Pytest"
        )
        async for _ in get_tracing_instrumentation_lifespan(
            tracing_config=tracing_config,
        )(app=app):
            pass


def install_package(package):
    pip.main(["install", package])


def uninstall_package(package):
    pip.main(["uninstall", "-y", package])


@pytest.fixture(scope="function")
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
    mocked_app: FastAPI,
    mock_otel_collector: InMemorySpanExporter,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
    manage_package,
):
    package_name = manage_package
    importlib.import_module(package_name)
    tracing_settings = TracingSettings()
    tracing_config = TracingConfig.create(
        tracing_settings=tracing_settings, service_name="Mock-Openetlemetry-Pytest"
    )
    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        # idempotency check
        async for _ in get_tracing_instrumentation_lifespan(
            tracing_config=tracing_config,
        )(app=mocked_app):
            pass


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "server_response",
    [
        PlainTextResponse("ok"),
        HTTPException(status_code=400, detail="error"),
    ],
)
async def test_trace_id_in_response_header(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: Callable,
    tracing_settings_in: Callable,
    server_response: PlainTextResponse | HTTPException,
) -> None:
    tracing_settings = TracingSettings()
    tracing_config = TracingConfig.create(
        tracing_settings=tracing_settings, service_name="Mock-Openetlemetry-Pytest"
    )

    handler_data = dict()

    async def handler(handler_data: dict):
        current_span = trace.get_current_span()
        handler_data[_OSPARC_TRACE_ID_HEADER] = format(
            current_span.get_span_context().trace_id, "032x"
        )
        if isinstance(server_response, HTTPException):
            raise server_response
        return server_response

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(
            mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True
        )
        client = TestClient(mocked_app)
        response = client.get("/")
        assert _OSPARC_TRACE_ID_HEADER in response.headers
        trace_id = response.headers[_OSPARC_TRACE_ID_HEADER]
        assert len(trace_id) == 32  # Ensure trace ID is a 32-character hex string
        assert trace_id == handler_data[_OSPARC_TRACE_ID_HEADER]


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "server_response",
    [
        PlainTextResponse("ok"),
        HTTPException(status_code=400, detail="error"),
    ],
)
async def test_with_profile_span(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable,
    server_response: PlainTextResponse | HTTPException,
):
    tracing_settings = TracingSettings()
    tracing_config = TracingConfig.create(
        tracing_settings=tracing_settings, service_name="Mock-Openetlemetry-Pytest"
    )

    handler_data = dict()

    async def handler(handler_data: dict):
        with profiled_span(tracing_config=tracing_config, span_name="my favorite span"):
            current_span = trace.get_current_span()
            handler_data[_OSPARC_TRACE_ID_HEADER] = format(
                current_span.get_span_context().trace_id, "032x"
            )
            if isinstance(server_response, HTTPException):
                raise server_response
            return server_response

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(
            mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True
        )
        client = TestClient(mocked_app)
        _ = client.get("/")
        trace_id = handler_data.get(_OSPARC_TRACE_ID_HEADER)
        assert trace_id is not None

        spans = mock_otel_collector.get_finished_spans()
        assert any(
            span.context.trace_id == int(trace_id, 16)
            and _PROFILE_ATTRIBUTE_NAME in span.attributes.keys()
            for span in spans
            if span.context is not None and span.attributes is not None
        )


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 0.05),
    ],
    indirect=True,
)
async def test_TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY_effective(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: Callable[[], None],
    tracing_settings_in: Callable[[], dict[str, Any]],
):
    """
    This test checks that the TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY setting in TracingSettings
    is effective by sending 1000 requests and verifying that the number of collected traces
    is close to 0.05 * 1000 (with some tolerance).
    """
    n_requests = 1000
    tolerance_probability = 0.5

    tracing_settings = TracingSettings()
    tracing_config = TracingConfig.create(
        tracing_settings=tracing_settings, service_name="Mock-OpenTelemetry-Pytest"
    )

    async def handler():
        return PlainTextResponse("ok")

    mocked_app.get("/")(handler)

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(
            mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True
        )
        client = TestClient(mocked_app)
        for _ in range(n_requests):
            client.get("/")
        trace_ids = {
            span.context.trace_id
            for span in mock_otel_collector.get_finished_spans()
            if span.context is not None
        }
        n_traces = len(trace_ids)
        expected_num_traces = int(
            tracing_settings.TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY * n_requests
        )
        # Allow a 50% tolerance due to randomness
        tolerance = int(tolerance_probability * expected_num_traces)
        assert (
            expected_num_traces - tolerance
            <= n_traces
            <= expected_num_traces + tolerance
        ), f"Expected roughly {expected_num_traces} distinct trace ids, got {n_traces}"


@pytest.fixture
def setup_logging_for_test(
    set_and_clean_settings_env_vars: Callable[[], None],
) -> TracingConfig:
    """Setup logging with tracing instrumentation before caplog captures logs."""
    tracing_settings = TracingSettings()
    tracing_config = TracingConfig.create(
        tracing_settings=tracing_settings, service_name="Mock-OpenTelemetry-Pytest"
    )

    # Setup logging with tracing instrumentation
    # This configures logging before caplog adds its handler
    setup_loggers(
        log_format_local_dev_enabled=False,
        logger_filter_mapping={},
        tracing_config=tracing_config,
        log_base_level=logging.INFO,
        noisy_loggers=None,
    )

    return tracing_config


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 0.05),
    ],
    indirect=True,
)
async def test_trace_id_in_logs_only_when_sampled(
    tracing_settings_in: Callable[[], dict[str, Any]],
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    setup_logging_for_test: TracingConfig,
    caplog: pytest.LogCaptureFixture,
):
    """
    This test verifies that trace IDs appear in logs only when the corresponding trace is sampled.
    With a low sampling probability (0.05), most requests won't be sampled, so their logs
    should not contain trace IDs.
    """
    n_requests = 200

    tracing_config = setup_logging_for_test

    test_logger = logging.getLogger("test_handler")
    caplog.set_level(logging.INFO, logger="test_handler")

    async def handler():
        test_logger.info("Handler executed")
        return PlainTextResponse("ok")

    mocked_app.get("/")(handler)

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(
            mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True
        )
        client = TestClient(mocked_app)

        for _ in range(n_requests):
            client.get("/")

        # Get all sampled trace IDs from the span exporter
        sampled_trace_ids = {
            format(span.context.trace_id, "032x")
            for span in mock_otel_collector.get_finished_spans()
            if span.context is not None
        }

        # Check log records
        trace_ids_in_logs = set()

        for record in caplog.records:
            if record.name == "test_handler":
                otel_trace_id = getattr(record, "otelTraceID", None)
                if otel_trace_id is not None and otel_trace_id != "0":
                    trace_ids_in_logs.add(otel_trace_id)

        tracing_settings = tracing_config.tracing_settings
        assert tracing_settings is not None
        assert (
            trace_ids_in_logs == sampled_trace_ids
        ), f"{tracing_settings.TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY=} | {n_requests=} | {len(sampled_trace_ids)=} | {len(trace_ids_in_logs)=}"
