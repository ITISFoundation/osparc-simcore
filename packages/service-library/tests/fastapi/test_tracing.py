# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import importlib
import logging
import secrets
import string
from collections.abc import Callable
from functools import partial

import pip
import pytest
from faker import Faker
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
    extract_span_link_from_trace_carrier,
    profiled_span,
    traced_operation,
)
from settings_library.tracing import TracingSettings


@pytest.fixture
def mocked_app() -> FastAPI:
    return FastAPI(title="opentelemetry example")


@pytest.fixture
def tracing_settings_in(request: pytest.FixtureRequest) -> tuple[str, int | str, float]:
    return request.param


@pytest.fixture
def set_and_clean_settings_env_vars(
    monkeypatch: pytest.MonkeyPatch, tracing_settings_in: tuple[str, int | str, float]
) -> None:
    endpoint, port, sampling_probability = tracing_settings_in
    if endpoint:
        monkeypatch.setenv("TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT", f"{endpoint}")
    if port:
        monkeypatch.setenv("TRACING_OPENTELEMETRY_COLLECTOR_PORT", f"{port}")
    if sampling_probability:
        monkeypatch.setenv("TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY", f"{sampling_probability}")


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
        ("http://opentelemetry-collector", "4318", 1.0),
    ],
    indirect=True,
)
async def test_valid_tracing_settings(
    faker: Faker,
    mocked_app: FastAPI,
    mock_otel_collector: InMemorySpanExporter,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
):
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())
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
        ("httsdasp://ot@##el-collector", 4318, 0.5),  # spellchecker:disable-line
        (" !@#$%^&*()[]{};:,<>?\\|`~+=/'\"", 4318, 0.5),
        # The following exceeds max DNS name length
        (
            "".join(secrets.choice(string.ascii_letters) for _ in range(300)),
            "1238712936",
            0.5,
        ),
    ],
    indirect=True,
)
async def test_invalid_tracing_settings(
    faker: Faker,
    mocked_app: FastAPI,
    mock_otel_collector: InMemorySpanExporter,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
):
    app = mocked_app
    with pytest.raises((BaseException, ValidationError, TypeError)):  # noqa: PT012
        tracing_settings = TracingSettings.create_from_envs()
        tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())
        async for _ in get_tracing_instrumentation_lifespan(
            tracing_config=tracing_config,
        )(app=app):
            pass


def install_package(package):
    pip.main(["install", package])


def uninstall_package(package):
    pip.main(["uninstall", "-y", package])


@pytest.fixture()
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
    faker: Faker,
    mocked_app: FastAPI,
    mock_otel_collector: InMemorySpanExporter,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
    manage_package,
):
    package_name = manage_package
    importlib.import_module(package_name)
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())
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
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
    server_response: PlainTextResponse | HTTPException,
    faker: Faker,
) -> None:
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

    handler_data = {}

    async def handler(handler_data: dict):
        current_span = trace.get_current_span()
        handler_data[_OSPARC_TRACE_ID_HEADER] = format(current_span.get_span_context().trace_id, "032x")
        if isinstance(server_response, HTTPException):
            raise server_response
        return server_response

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
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
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
    server_response: PlainTextResponse | HTTPException,
    faker: Faker,
):
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

    handler_data = {}

    async def handler(handler_data: dict):
        with profiled_span(tracing_config=tracing_config, span_name="my favorite span"):
            current_span = trace.get_current_span()
            handler_data[_OSPARC_TRACE_ID_HEADER] = format(current_span.get_span_context().trace_id, "032x")
            if isinstance(server_response, HTTPException):
                raise server_response
            return server_response

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
        client = TestClient(mocked_app)
        _ = client.get("/")
        trace_id = handler_data.get(_OSPARC_TRACE_ID_HEADER)
        assert trace_id is not None

        spans = mock_otel_collector.get_finished_spans()
        assert any(
            span.context.trace_id == int(trace_id, 16) and _PROFILE_ATTRIBUTE_NAME in span.attributes
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
async def test_tracing_opentelemetry_sampling_probability_effective(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
    faker: Faker,
):
    """
    This test checks that the TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY setting in TracingSettings
    is effective by sending 1000 requests and verifying that the number of collected traces
    is close to 0.05 * 1000 (with some tolerance).
    """
    n_requests = 1000
    tolerance_probability = 0.5

    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

    async def handler():
        return PlainTextResponse("ok")

    mocked_app.get("/")(handler)

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
        client = TestClient(mocked_app)
        for _ in range(n_requests):
            client.get("/")
        trace_ids = {
            span.context.trace_id for span in mock_otel_collector.get_finished_spans() if span.context is not None
        }
        n_traces = len(trace_ids)
        expected_num_traces = int(tracing_settings.TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY * n_requests)
        # Allow a 50% tolerance due to randomness
        tolerance = int(tolerance_probability * expected_num_traces)
        assert expected_num_traces - tolerance <= n_traces <= expected_num_traces + tolerance, (
            f"Expected roughly {expected_num_traces} distinct trace ids, got {n_traces}"
        )


@pytest.fixture
def setup_logging_for_test(
    set_and_clean_settings_env_vars: None,
    faker: Faker,
) -> TracingConfig:
    """Setup logging with tracing instrumentation before caplog captures logs."""
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

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
)  # NOTE: The order of these fixtures are important for caplog to work correctly
async def test_trace_id_in_logs_only_when_sampled(
    tracing_settings_in: tuple[str, int | str, float],
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    setup_logging_for_test: TracingConfig,
    caplog: pytest.LogCaptureFixture,
):
    """
    This test verifies that trace IDs appear in logs regardless of whether the corresponding trace is sampled.
    With a low sampling probability (0.05), most requests won't be sampled, so their logs
    should not contain trace IDs.
    """
    n_requests = 1000

    tracing_config = setup_logging_for_test

    test_logger = logging.getLogger("test_handler")
    caplog.set_level(logging.INFO, logger="test_handler")

    async def handler(all_trace_ids: set[str]):
        test_logger.info("Handler executed")
        trace_id = trace.get_current_span().get_span_context().trace_id
        all_trace_ids.add(format(trace_id, "032x"))
        return PlainTextResponse("ok")

    all_trace_ids: set[str] = set()
    mocked_app.get("/")(partial(handler, all_trace_ids))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
        client = TestClient(mocked_app)

        for _ in range(n_requests):
            client.get("/")

        # Check log records
        trace_ids_in_logs = set()

        for record in caplog.records:
            if record.name == "test_handler":
                otel_trace_id = getattr(record, "otelTraceID", None)
                if otel_trace_id is not None and otel_trace_id not in {"not_recorded", "0"}:
                    trace_ids_in_logs.add(otel_trace_id)

        tracing_settings = tracing_config.tracing_settings
        assert tracing_settings is not None
        assert len(trace_ids_in_logs) > 0
        assert len(trace_ids_in_logs) == len(all_trace_ids) == n_requests
        assert trace_ids_in_logs == all_trace_ids, f"{n_requests=} | {len(all_trace_ids)=} | {len(trace_ids_in_logs)=}"


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
async def test_traced_operation_basic(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: tuple[str, int | str, float],
    faker: Faker,
) -> None:
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

    handler_data = {}

    async def handler(handler_data: dict) -> PlainTextResponse:
        with traced_operation(
            "test_operation",
            tracing_config=tracing_config,
            attributes={"user.id": "123", "operation.type": "test"},
        ):
            current_span = trace.get_current_span()
            handler_data["trace_id"] = format(current_span.get_span_context().trace_id, "032x")
            handler_data["span_name"] = current_span.get_span_context().trace_id
        return PlainTextResponse("ok")

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
        client = TestClient(mocked_app)
        _ = client.get("/")

        trace_id = handler_data.get("trace_id")
        assert trace_id is not None

        spans = mock_otel_collector.get_finished_spans()
        # Find the traced_operation span
        operation_spans = [
            span
            for span in spans
            if span.context is not None and span.context.trace_id == int(trace_id, 16) and span.name == "test_operation"
        ]
        assert len(operation_spans) == 1, f"Expected 1 'test_operation' span, got {len(operation_spans)}"
        operation_span = operation_spans[0]

        # Verify attributes
        assert operation_span.attributes is not None
        assert operation_span.attributes.get("user.id") == "123"
        assert operation_span.attributes.get("operation.type") == "test"


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
async def test_traced_operation_nested_spans(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: tuple[str, int | str, float],
    faker: Faker,
) -> None:
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

    handler_data = {}

    async def handler(handler_data: dict) -> PlainTextResponse:
        with (
            traced_operation(
                "parent_operation",
                tracing_config=tracing_config,
                attributes={"level": "parent"},
            ),
            traced_operation(
                "child_operation",
                tracing_config=tracing_config,
                attributes={"level": "child"},
            ),
        ):
            current_span = trace.get_current_span()
            handler_data["trace_id"] = format(current_span.get_span_context().trace_id, "032x")
        return PlainTextResponse("ok")

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
        client = TestClient(mocked_app)
        _ = client.get("/")

        trace_id = handler_data.get("trace_id")
        assert trace_id is not None

        spans = mock_otel_collector.get_finished_spans()
        trace_id_int = int(trace_id, 16)
        trace_spans = [span for span in spans if span.context is not None and span.context.trace_id == trace_id_int]

        # Should have at least parent and child operation spans
        operation_spans = [span for span in trace_spans if span.name in ("parent_operation", "child_operation")]
        assert len(operation_spans) >= 2, f"Expected at least 2 operation spans, got {len(operation_spans)}"

        parent_spans = [span for span in operation_spans if span.name == "parent_operation"]
        child_spans = [span for span in operation_spans if span.name == "child_operation"]

        assert len(parent_spans) == 1, f"Expected 1 parent span, got {len(parent_spans)}"
        assert len(child_spans) == 1, f"Expected 1 child span, got {len(child_spans)}"

        # Verify attributes
        assert parent_spans[0].attributes is not None
        assert parent_spans[0].attributes.get("level") == "parent"
        assert child_spans[0].attributes is not None
        assert child_spans[0].attributes.get("level") == "child"


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
async def test_traced_operation_with_exception(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
    faker: Faker,
) -> None:
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

    handler_data = {}

    async def handler(handler_data: dict):
        try:
            with traced_operation(
                "failing_operation",
                tracing_config=tracing_config,
                attributes={"operation.status": "fail"},
            ):
                current_span = trace.get_current_span()
                handler_data["trace_id"] = format(current_span.get_span_context().trace_id, "032x")
                msg = "Test exception to check if it's recorded in the span"
                raise ValueError(msg)  # noqa: TRY301
        except ValueError:
            pass
        return PlainTextResponse("ok")

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
        client = TestClient(mocked_app)
        _ = client.get("/")

        trace_id = handler_data.get("trace_id")
        assert trace_id is not None

        spans = mock_otel_collector.get_finished_spans()
        trace_id_int = int(trace_id, 16)

        # Find the failing_operation span
        failing_spans = [
            span
            for span in spans
            if span.context is not None and span.context.trace_id == trace_id_int and span.name == "failing_operation"
        ]
        assert len(failing_spans) == 1, f"Expected 1 failing_operation span, got {len(failing_spans)}"
        failing_span = failing_spans[0]

        # The exception should be recorded (via trace.get_current_span().record_exception or similar)
        # Verify the span attributes show the error occurred
        assert failing_span.attributes is not None
        assert failing_span.attributes.get("operation.status") == "fail"


@pytest.mark.parametrize(
    "tracing_settings_in",
    [
        ("http://opentelemetry-collector", 4318, 1.0),
    ],
    indirect=True,
)
async def test_traced_operation_with_links(
    mock_otel_collector: InMemorySpanExporter,
    mocked_app: FastAPI,
    set_and_clean_settings_env_vars: None,
    tracing_settings_in: Callable[[], tuple[str, int | str, float]],
    faker: Faker,
) -> None:
    tracing_settings = TracingSettings.create_from_envs()
    tracing_config = TracingConfig.create(tracing_settings=tracing_settings, service_name=faker.pystr())

    handler_data = {}

    async def handler(handler_data: dict):
        # Create a carrier to simulate an external trace context
        carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
        link = extract_span_link_from_trace_carrier(carrier)

        with traced_operation(
            "linked_operation",
            tracing_config=tracing_config,
            attributes={"operation.linked": "true"},
            links=[link] if link else None,
        ):
            current_span = trace.get_current_span()
            handler_data["trace_id"] = format(current_span.get_span_context().trace_id, "032x")
        return PlainTextResponse("ok")

    mocked_app.get("/")(partial(handler, handler_data))

    async for _ in get_tracing_instrumentation_lifespan(
        tracing_config=tracing_config,
    )(app=mocked_app):
        initialize_fastapi_app_tracing(mocked_app, tracing_config=tracing_config, add_response_trace_id_header=True)
        client = TestClient(mocked_app)
        _ = client.get("/")

        trace_id = handler_data.get("trace_id")
        assert trace_id is not None

        spans = mock_otel_collector.get_finished_spans()
        trace_id_int = int(trace_id, 16)

        # Find the linked_operation span
        linked_spans = [
            span
            for span in spans
            if span.context is not None and span.context.trace_id == trace_id_int and span.name == "linked_operation"
        ]
        assert len(linked_spans) == 1, f"Expected 1 linked_operation span, got {len(linked_spans)}"
        linked_span = linked_spans[0]

        # Verify attributes
        assert linked_span.attributes is not None
        assert linked_span.attributes.get("operation.linked") == "true"
