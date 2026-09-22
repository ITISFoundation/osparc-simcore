# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from collections.abc import Iterator

import pytest
from opentelemetry import metrics
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.metrics._internal import _ProxyMeterProvider
from servicelib.tracing import setup_meter_provider

_INSTRUMENTATION_NAME = "some.instrumentation.library"


def _retained_meter_count(provider: _ProxyMeterProvider) -> int:
    return len(provider._meters)  # noqa: SLF001


@pytest.fixture
def isolated_otel_meter_provider() -> Iterator[_ProxyMeterProvider]:
    """Gives each test a pristine global meter provider.

    The OpenTelemetry meter provider is a process-wide global that can only be
    set once, so it must be saved and restored around every test.
    """
    otel_metrics = metrics._internal  # noqa: SLF001
    saved_provider = otel_metrics._METER_PROVIDER  # noqa: SLF001
    saved_proxy = otel_metrics._PROXY_METER_PROVIDER  # noqa: SLF001

    fresh_proxy = _ProxyMeterProvider()
    otel_metrics._METER_PROVIDER = None  # noqa: SLF001
    otel_metrics._PROXY_METER_PROVIDER = fresh_proxy  # noqa: SLF001

    yield fresh_proxy

    otel_metrics._METER_PROVIDER = saved_provider  # noqa: SLF001
    otel_metrics._PROXY_METER_PROVIDER = saved_proxy  # noqa: SLF001


def test_proxy_meter_provider_retains_every_meter(
    isolated_otel_meter_provider: _ProxyMeterProvider,
):
    # documents the leak `setup_meter_provider` exists to prevent: instrumentors
    # call get_meter() on every client construction
    assert isinstance(metrics.get_meter_provider(), _ProxyMeterProvider)

    for _ in range(10):
        metrics.get_meter(_INSTRUMENTATION_NAME, "1.0")

    assert _retained_meter_count(isolated_otel_meter_provider) == 10


def test_setup_meter_provider_stops_meter_retention(
    isolated_otel_meter_provider: _ProxyMeterProvider,
):
    setup_meter_provider()

    assert isinstance(metrics.get_meter_provider(), NoOpMeterProvider)

    for _ in range(100):
        meter = metrics.get_meter(_INSTRUMENTATION_NAME, "1.0")
        meter.create_histogram("some.duration", unit="s")

    assert _retained_meter_count(isolated_otel_meter_provider) == 0


def test_setup_meter_provider_is_idempotent(
    isolated_otel_meter_provider: _ProxyMeterProvider,
):
    setup_meter_provider()
    first_provider = metrics.get_meter_provider()

    setup_meter_provider()

    assert metrics.get_meter_provider() is first_provider
