from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter

from opentelemetry import trace
from prometheus_client import (
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)
from prometheus_client.registry import CollectorRegistry

#
# CAUTION CAUTION CAUTION NOTE:
# Be very careful with metrics. pay attention to metrics cardinatity.
# Each time series takes about 3kb of overhead in Prometheus
#
# CAUTION: every unique combination of key-value label pairs represents a new time series
#
# If a metrics is not needed, don't add it!! It will collapse the application AND prometheus
#
# references:
# https://prometheus.io/docs/practices/naming/
# https://www.robustperception.io/cardinality-is-key
# https://www.robustperception.io/why-does-prometheus-use-so-much-ram
# https://promcon.io/2019-munich/slides/containing-your-cardinality.pdf
# https://grafana.com/docs/grafana-cloud/how-do-i/control-prometheus-metrics-usage/usage-analysis-explore/
#


@dataclass
class PrometheusMetrics:
    registry: CollectorRegistry
    process_collector: ProcessCollector
    platform_collector: PlatformCollector
    gc_collector: GCCollector
    request_count: Counter
    in_flight_requests: Gauge
    response_latency_with_labels: Histogram
    response_latency_detailed_buckets: Histogram


def _get_exemplar() -> dict[str, str] | None:
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        return None
    trace_id = trace.format_trace_id(current_span.get_span_context().trace_id)
    return {"TraceID": trace_id}


def setup_prometheus_metrics() -> PrometheusMetrics:
    # app-scope registry
    registry = CollectorRegistry(auto_describe=False)

    # automatically collects process metrics
    process_collector = ProcessCollector(registry=registry)
    # automatically collects python_info metrics
    platform_collector = PlatformCollector(registry=registry)
    # automatically collects python garbage collector metrics
    gc_collector = GCCollector(registry=registry)

    # Total number of requests processed
    request_count = Counter(
        name="http_requests",
        documentation="Total requests count",
        labelnames=[
            "method",
            "endpoint",
            "http_status",
            "simcore_user_agent",
        ],
        registry=registry,
    )

    in_flight_requests = Gauge(
        name="http_in_flight_requests",
        documentation="Number of requests in process",
        labelnames=["method", "endpoint", "simcore_user_agent"],
        registry=registry,
    )

    response_latency_with_labels = Histogram(
        name="http_request_latency_seconds_with_labels",
        documentation="Time processing a request with detailed labels",
        labelnames=["method", "endpoint", "simcore_user_agent"],
        registry=registry,
        buckets=(0.1, 0.5, 1),
    )

    response_latency_detailed_buckets = Histogram(
        name="http_request_latency_seconds_detailed_buckets",
        documentation="Time processing a request with detailed buckets but no labels",
        registry=registry,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    )

    return PrometheusMetrics(
        registry=registry,
        process_collector=process_collector,
        platform_collector=platform_collector,
        gc_collector=gc_collector,
        request_count=request_count,
        in_flight_requests=in_flight_requests,
        response_latency_with_labels=response_latency_with_labels,
        response_latency_detailed_buckets=response_latency_detailed_buckets,
    )


@contextmanager
def record_request_metrics(
    *,
    metrics: PrometheusMetrics,
    method: str,
    endpoint: str,
    user_agent: str,
) -> Iterator[None]:
    """
    Context manager to record Prometheus metrics for a request.

    Args:
        metrics (PrometheusMetrics): The Prometheus metrics instance.
        app_name (str): The application name.
        method (str): The HTTP method.
        endpoint (str): The canonical endpoint.
        user_agent (str): The user agent header value.
    """

    with metrics.in_flight_requests.labels(
        method, endpoint, user_agent
    ).track_inprogress():

        start = perf_counter()

        yield

        amount = perf_counter() - start
        exemplar = _get_exemplar()
        metrics.response_latency_with_labels.labels(
            method, endpoint, user_agent
        ).observe(amount=amount, exemplar=exemplar)
        metrics.response_latency_detailed_buckets.observe(
            amount=amount, exemplar=exemplar
        )


def record_response_metrics(
    *,
    metrics: PrometheusMetrics,
    method: str,
    endpoint: str,
    user_agent: str,
    http_status: int,
) -> None:
    exemplar = _get_exemplar()
    metrics.request_count.labels(method, endpoint, http_status, user_agent).inc(
        exemplar=exemplar
    )
