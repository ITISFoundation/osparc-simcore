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
