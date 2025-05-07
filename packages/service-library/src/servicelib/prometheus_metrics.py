from prometheus_client import (
    Counter,
    Gauge,
    GCCollector,
    PlatformCollector,
    ProcessCollector,
    Summary,
)
from prometheus_client.registry import CollectorRegistry

kREQUEST_COUNT = f"{__name__}.request_count"  # noqa: N816
kINFLIGHTREQUESTS = f"{__name__}.in_flight_requests"  # noqa: N816
kRESPONSELATENCY = f"{__name__}.in_response_latency"  # noqa: N816

kCOLLECTOR_REGISTRY = f"{__name__}.collector_registry"  # noqa: N816
kPROCESS_COLLECTOR = f"{__name__}.collector_process"  # noqa: N816
kPLATFORM_COLLECTOR = f"{__name__}.collector_platform"  # noqa: N816
kGC_COLLECTOR = f"{__name__}.collector_gc"  # noqa: N816


def setup_prometheus_metrics(app, app_name: str, **app_info_kwargs):
    # app-scope registry
    target_info = {"application_name": app_name}
    target_info.update(app_info_kwargs)
    app[kCOLLECTOR_REGISTRY] = reg = CollectorRegistry(
        auto_describe=False, target_info=target_info
    )
    # automatically collects process metrics
    app[kPROCESS_COLLECTOR] = ProcessCollector(registry=reg)
    # automatically collects python_info metrics
    app[kPLATFORM_COLLECTOR] = PlatformCollector(registry=reg)
    # automatically collects python garbage collector metrics
    app[kGC_COLLECTOR] = GCCollector(registry=reg)

    # Total number of requests processed
    app[kREQUEST_COUNT] = Counter(
        name="http_requests",
        documentation="Total requests count",
        labelnames=[
            "app_name",
            "method",
            "endpoint",
            "http_status",
            "simcore_user_agent",
        ],
        registry=reg,
    )

    app[kINFLIGHTREQUESTS] = Gauge(
        name="http_in_flight_requests",
        documentation="Number of requests in process",
        labelnames=["app_name", "method", "endpoint", "simcore_user_agent"],
        registry=reg,
    )

    app[kRESPONSELATENCY] = Summary(
        name="http_request_latency_seconds",
        documentation="Time processing a request",
        labelnames=["app_name", "method", "endpoint", "simcore_user_agent"],
        registry=reg,
    )
