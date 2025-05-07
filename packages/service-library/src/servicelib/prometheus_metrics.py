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


# This creates the following basic metrics:
# # HELP process_virtual_memory_bytes Virtual memory size in bytes.
# # TYPE process_virtual_memory_bytes gauge
# process_virtual_memory_bytes 8.12425216e+08
# # HELP process_resident_memory_bytes Resident memory size in bytes.
# # TYPE process_resident_memory_bytes gauge
# process_resident_memory_bytes 1.2986368e+08
# # HELP process_start_time_seconds Start time of the process since unix epoch in seconds.
# # TYPE process_start_time_seconds gauge
# process_start_time_seconds 1.6418063518e+09
# # HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.
# # TYPE process_cpu_seconds_total counter
# process_cpu_seconds_total 9.049999999999999
# # HELP process_open_fds Number of open file descriptors.
# # TYPE process_open_fds gauge
# process_open_fds 29.0
# # HELP process_max_fds Maximum number of open file descriptors.
# # TYPE process_max_fds gauge
# process_max_fds 1.048576e+06
# # HELP python_info Python platform information
# # TYPE python_info gauge
# python_info{implementation="CPython",major="3",minor="8",patchlevel="10",version="3.9.12"} 1.0
# # HELP python_gc_objects_collected_total Objects collected during gc
# # TYPE python_gc_objects_collected_total counter
# python_gc_objects_collected_total{generation="0"} 7328.0
# python_gc_objects_collected_total{generation="1"} 614.0
# python_gc_objects_collected_total{generation="2"} 0.0
# # HELP python_gc_objects_uncollectable_total Uncollectable object found during GC
# # TYPE python_gc_objects_uncollectable_total counter
# python_gc_objects_uncollectable_total{generation="0"} 0.0
# python_gc_objects_uncollectable_total{generation="1"} 0.0
# python_gc_objects_uncollectable_total{generation="2"} 0.0
# # HELP python_gc_collections_total Number of times this generation was collected
# # TYPE python_gc_collections_total counter
# python_gc_collections_total{generation="0"} 628.0
# python_gc_collections_total{generation="1"} 57.0
# python_gc_collections_total{generation="2"} 5.0
# # HELP http_requests_total Total requests count
# # TYPE http_requests_total counter
# http_requests_total{app_name="simcore_service_webserver",endpoint="/v0/",http_status="200",method="GET"} 15.0
# # HELP http_requests_created Total requests count
# # TYPE http_requests_created gauge
# http_requests_created{app_name="simcore_service_webserver",endpoint="/v0/",http_status="200",method="GET"} 1.6418063614890063e+09
# # HELP http_in_flight_requests Number of requests in process
# # TYPE http_in_flight_requests gauge
# http_in_flight_requests{app_name="simcore_service_webserver",endpoint="/v0/",method="GET"} 0.0
# http_in_flight_requests{app_name="simcore_service_webserver",endpoint="/metrics",method="GET"} 1.0
# # HELP http_request_latency_seconds Time processing a request
# # TYPE http_request_latency_seconds summary
# http_request_latency_seconds_count{app_name="simcore_service_webserver",endpoint="/v0/",method="GET"} 15.0
# http_request_latency_seconds_sum{app_name="simcore_service_webserver",endpoint="/v0/",method="GET"} 0.007384857000033662
# http_request_latency_seconds_count{app_name="simcore_service_webserver",endpoint="/metrics",method="GET"} 0.0
# http_request_latency_seconds_sum{app_name="simcore_service_webserver",endpoint="/metrics",method="GET"} 0.0
# # HELP http_request_latency_seconds_created Time processing a request
# # TYPE http_request_latency_seconds_created gauge
# http_request_latency_seconds_created{app_name="simcore_service_webserver",endpoint="/v0/",method="GET"} 1.6418063614873598e+09
# http_request_latency_seconds_created{app_name="simcore_service_webserver",endpoint="/metrics",method="GET"} 1.641806371709292e+09


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

    response_latency_with_labels = Histogram(
        name="http_request_latency_seconds_with_labels",
        documentation="Time processing a request with detailed labels",
        labelnames=["app_name", "method", "endpoint", "simcore_user_agent"],
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
    ).track_inprogress():

        start = perf_counter()

        yield

        amount = perf_counter() - start
        exemplar = _get_exemplar()
        metrics.response_latency_with_labels.labels(
            app_name, method, endpoint, user_agent
        ).observe(amount=amount, exemplar=exemplar)
        metrics.response_latency_detailed_buckets.labels(
            app_name, method, endpoint, user_agent
        ).observe(amount=amount, exemplar=exemplar)


def record_response_metrics(
    *,
    metrics: PrometheusMetrics,
    app_name: str,
    method: str,
    endpoint: str,
    user_agent: str,
    http_status: int,
) -> None:
    exemplar = _get_exemplar()
    metrics.request_count.labels(
        app_name, method, endpoint, http_status, user_agent
    ).inc(exemplar=exemplar)
