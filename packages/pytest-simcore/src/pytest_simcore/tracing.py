import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest_mock import MockerFixture


@pytest.fixture
async def mock_otel_collector_fastapi(mocker: MockerFixture) -> InMemorySpanExporter:
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    mocker.patch(
        "servicelib.fastapi.tracing._create_span_processor", return_value=span_processor
    )
    return memory_exporter
