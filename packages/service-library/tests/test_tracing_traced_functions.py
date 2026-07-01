# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import sys
import types
from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from servicelib.traced_functions_instrumentor import (
    _parse_traced_function_targets,
    instrument_traced_functions,
    uninstrument_traced_functions,
)

_SAMPLE_MODULE_NAME = "_servicelib_traced_functions_sample"


@pytest.fixture
def sample_module() -> Iterator[types.ModuleType]:
    module = types.ModuleType(_SAMPLE_MODULE_NAME)

    async def async_double(value: int) -> int:
        return value * 2

    def sync_increment(value: int) -> int:
        return value + 1

    module.async_double = async_double  # type: ignore[attr-defined]
    module.sync_increment = sync_increment  # type: ignore[attr-defined]
    sys.modules[_SAMPLE_MODULE_NAME] = module
    try:
        yield module
    finally:
        sys.modules.pop(_SAMPLE_MODULE_NAME, None)


@pytest.fixture
def in_memory_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def tracer_provider(in_memory_exporter: InMemorySpanExporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(in_memory_exporter))
    return provider


def test__parse_traced_function_targets_splits_and_strips():
    assert _parse_traced_function_targets([]) == []
    assert _parse_traced_function_targets([""]) == []
    assert _parse_traced_function_targets(["a.b:c", "d.e:F.g"]) == ["a.b:c", "d.e:F.g"]


def test_instrument_traced_functions_creates_spans_for_sync_and_async(
    sample_module: types.ModuleType,
    tracer_provider: TracerProvider,
    in_memory_exporter: InMemorySpanExporter,
):
    specs = [
        f"{_SAMPLE_MODULE_NAME}:async_double",
        f"{_SAMPLE_MODULE_NAME}:sync_increment",
    ]
    wrapped = instrument_traced_functions(specs, tracer_provider=tracer_provider)
    try:
        assert asyncio.run(sample_module.async_double(3)) == 6
        assert sample_module.sync_increment(3) == 4

        span_names = {span.name for span in in_memory_exporter.get_finished_spans()}
        assert f"{_SAMPLE_MODULE_NAME}:async_double" in span_names
        assert f"{_SAMPLE_MODULE_NAME}:sync_increment" in span_names
    finally:
        uninstrument_traced_functions(wrapped)


def test_instrument_traced_functions_skips_invalid_targets(
    tracer_provider: TracerProvider,
    in_memory_exporter: InMemorySpanExporter,
):
    wrapped = instrument_traced_functions(
        ["nonexistent.module:func", f"{_SAMPLE_MODULE_NAME}:not_defined"],
        tracer_provider=tracer_provider,
    )
    assert wrapped == []
    assert in_memory_exporter.get_finished_spans() == ()


def test_uninstrument_traced_functions_restores_original(
    sample_module: types.ModuleType,
    tracer_provider: TracerProvider,
    in_memory_exporter: InMemorySpanExporter,
):
    spec = f"{_SAMPLE_MODULE_NAME}:sync_increment"
    wrapped = instrument_traced_functions([spec], tracer_provider=tracer_provider)
    assert sample_module.sync_increment(1) == 2

    uninstrument_traced_functions(wrapped)
    in_memory_exporter.clear()

    assert sample_module.sync_increment(1) == 2
    assert in_memory_exporter.get_finished_spans() == ()
