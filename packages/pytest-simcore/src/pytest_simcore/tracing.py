import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest_mock import MockerFixture


@pytest.fixture
async def setup_tracing_fastapi(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> InMemorySpanExporter:
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    mocker.patch(
        "servicelib.fastapi.tracing._create_span_processor", return_value=span_processor
    )

    monkeypatch.setenv(
        "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT", "http://opentelemetry-collector"
    )
    monkeypatch.setenv("TRACING_OPENTELEMETRY_COLLECTOR_PORT", "4318")
    return memory_exporter


@pytest.fixture
async def setup_tracing_aiohttp(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> InMemorySpanExporter:
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    mocker.patch(
        "servicelib.aiohttp.tracing._create_span_processor", return_value=span_processor
    )

    monkeypatch.setenv(
        "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT", "http://opentelemetry-collector"
    )
    monkeypatch.setenv("TRACING_OPENTELEMETRY_COLLECTOR_PORT", "4318")
    return memory_exporter
