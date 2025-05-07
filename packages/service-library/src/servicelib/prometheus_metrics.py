from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from prometheus_client import (
    Counter,
    Gauge,
    GCCollector,
    PlatformCollector,
    ProcessCollector,
    Summary,
)
from prometheus_client.registry import CollectorRegistry


@dataclass
class PrometheusMetrics:
    registry: CollectorRegistry
    process_collector: ProcessCollector
    platform_collector: PlatformCollector
    gc_collector: GCCollector
    request_count: Counter
    in_flight_requests: Gauge
    response_latency: Summary


def setup_prometheus_metrics(app_name: str, **app_info_kwargs) -> PrometheusMetrics:
    # app-scope registry
    target_info = {"application_name": app_name}
    target_info.update(app_info_kwargs)
    registry = CollectorRegistry(auto_describe=False, target_info=target_info)

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
            "app_name",
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
        labelnames=["app_name", "method", "endpoint", "simcore_user_agent"],
        registry=registry,
    )

    response_latency = Summary(
        name="http_request_latency_seconds",
        documentation="Time processing a request",
        labelnames=["app_name", "method", "endpoint", "simcore_user_agent"],
        registry=registry,
    )

    return PrometheusMetrics(
        registry=registry,
        process_collector=process_collector,
        platform_collector=platform_collector,
        gc_collector=gc_collector,
        request_count=request_count,
        in_flight_requests=in_flight_requests,
        response_latency=response_latency,
    )


@contextmanager
def record_request_metrics(
    *,
    metrics: PrometheusMetrics,
    app_name: str,
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
        app_name, method, endpoint, user_agent
    ).track_inprogress(), metrics.response_latency.labels(
        app_name, method, endpoint, user_agent
    ).time():
        yield


def record_response_metrics(
    *,
    metrics: PrometheusMetrics,
    app_name: str,
    method: str,
    endpoint: str,
    user_agent: str,
    status_code: int,
) -> None:
    metrics.request_count.labels(
        app_name, method, endpoint, status_code, user_agent
    ).inc()
