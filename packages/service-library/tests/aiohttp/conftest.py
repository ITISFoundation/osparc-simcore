# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import Iterator
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest_mock import MockerFixture


@pytest.fixture
def mock_otel_collector(mocker: MockerFixture) -> Iterator[InMemorySpanExporter]:
    memory_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(memory_exporter)
    with patch(
        "servicelib.aiohttp.tracing._create_span_processor", return_value=span_processor
    ):
        yield memory_exporter
