""" Enables monitoring of some quantities needed for diagnostics

"""

import asyncio
import logging
import time
from typing import Awaitable, Callable

import prometheus_client
from aiohttp import web
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    GCCollector,
    PlatformCollector,
    ProcessCollector,
    Summary,
)
from prometheus_client.registry import CollectorRegistry
from servicelib.aiohttp.typing_extension import Handler

from ..common_headers import (
    UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE,
    X_SIMCORE_USER_AGENT,
)
from ..logging_utils import log_catch

log = logging.getLogger(__name__)


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


kREQUEST_COUNT = f"{__name__}.request_count"
kINFLIGHTREQUESTS = f"{__name__}.in_flight_requests"
kRESPONSELATENCY = f"{__name__}.in_response_latency"

kCOLLECTOR_REGISTRY = f"{__name__}.collector_registry"
kPROCESS_COLLECTOR = f"{__name__}.collector_process"
kPLATFORM_COLLECTOR = f"{__name__}.collector_platform"
kGC_COLLECTOR = f"{__name__}.collector_gc"


def get_collector_registry(app: web.Application) -> CollectorRegistry:
    return app[kCOLLECTOR_REGISTRY]


async def metrics_handler(request: web.Request):
    registry = get_collector_registry(request.app)

    # NOTE: Cannot use ProcessPoolExecutor because registry is not pickable
    result = await asyncio.get_event_loop().run_in_executor(
        None, prometheus_client.generate_latest, registry
    )
    response = web.Response(body=result)
    response.content_type = CONTENT_TYPE_LATEST
    return response


EnterMiddlewareCB = Callable[[web.Request], Awaitable[None]]
ExitMiddlewareCB = Callable[[web.Request, web.StreamResponse], Awaitable[None]]


def middleware_factory(
    app_name: str,
    enter_middleware_cb: EnterMiddlewareCB | None,
    exit_middleware_cb: ExitMiddlewareCB | None,
):
    @web.middleware
    async def middleware_handler(request: web.Request, handler: Handler):
        # See https://prometheus.io/docs/concepts/metric_types

        log_exception = None
        resp: web.StreamResponse = web.HTTPInternalServerError(
            reason="Unexpected exception"
        )
        # NOTE: a canonical endpoint is `/v0/projects/{project_id}/node/{node_uuid}``
        # vs a resolved endpoint `/v0/projects/51e4bdf4-2cc7-43be-85a6-627a4c0afb77/nodes/51e4bdf4-2cc7-43be-85a6-627a4c0afb77`
        # which would create way to many different endpoints for monitoring!
        canonical_endpoint = request.path
        if request.match_info.route.resource:
            canonical_endpoint = request.match_info.route.resource.canonical
        start_time = time.time()
        try:
            if enter_middleware_cb:
                with log_catch(logger=log, reraise=False):
                    await enter_middleware_cb(request)

            in_flight_gauge = request.app[kINFLIGHTREQUESTS]
            response_summary = request.app[kRESPONSELATENCY]

            with in_flight_gauge.labels(
                app_name,
                request.method,
                canonical_endpoint,
                request.headers.get(
                    X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                ),
            ).track_inprogress(), response_summary.labels(
                app_name,
                request.method,
                canonical_endpoint,
                request.headers.get(
                    X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                ),
            ).time():
                resp = await handler(request)

            assert isinstance(  # nosec
                resp, web.StreamResponse
            ), "Forgot envelope middleware?"

        except web.HTTPServerError as exc:
            # Transforms exception into response object and log exception
            resp = exc
            log_exception = exc
        except web.HTTPException as exc:
            # Transforms non-HTTPServerError exceptions into response object
            resp = exc
            log_exception = None
        except asyncio.CancelledError as exc:
            # Mostly for logging
            resp = web.HTTPInternalServerError(reason=f"{exc}")
            log_exception = exc
            raise
        except Exception as exc:  # pylint: disable=broad-except
            # Prevents issue #1025.
            resp = web.HTTPInternalServerError(reason=f"{exc}")
            resp.__cause__ = exc
            log_exception = exc

        finally:
            resp_time_secs: float = time.time() - start_time

            # prometheus probes
            request.app[kREQUEST_COUNT].labels(
                app_name,
                request.method,
                canonical_endpoint,
                resp.status,
                request.headers.get(
                    X_SIMCORE_USER_AGENT, UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                ),
            ).inc()

            if exit_middleware_cb:
                with log_catch(logger=log, reraise=False):
                    await exit_middleware_cb(request, resp)

            if log_exception:
                log.error(
                    'Unexpected server error "%s" from access: %s "%s %s" done '
                    "in %3.2f secs. Responding with status %s",
                    type(log_exception),
                    request.remote,
                    request.method,
                    request.path,
                    resp_time_secs,
                    resp.status,
                    exc_info=log_exception,
                    stack_info=True,
                )

        return resp

    # adds identifier
    middleware_handler.__middleware_name__ = f"{__name__}.monitor_{app_name}"

    return middleware_handler


def setup_monitoring(
    app: web.Application,
    app_name: str,
    *,
    enter_middleware_cb: EnterMiddlewareCB | None = None,
    exit_middleware_cb: ExitMiddlewareCB | None = None,
    **app_info_kwargs,
):
    # app-scope registry
    target_info = {"application_name": app_name}
    target_info.update(app_info_kwargs)
    app[kCOLLECTOR_REGISTRY] = reg = CollectorRegistry(
        auto_describe=False, target_info=target_info
    )
    # automatically collects process metrics see [https://github.com/prometheus/client_python]
    app[kPROCESS_COLLECTOR] = ProcessCollector(registry=reg)
    # automatically collects python_info metrics see [https://github.com/prometheus/client_python]
    app[kPLATFORM_COLLECTOR] = PlatformCollector(registry=reg)
    # automatically collects python garbage collector metrics see [https://github.com/prometheus/client_python]
    # prefixed with python_gc_
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

    # WARNING: ensure ERROR middleware is over this one
    #
    # non-API request/response (e.g /metrics, /x/*  ...)
    #                                 |
    # API request/response (/v0/*)    |
    #       |                         |
    #       |                         |
    #       v                         |
    # ===== monitoring-middleware =====
    # == rest-error-middlewarer ====  |
    # ==           ...            ==  |
    # == rest-envelope-middleware ==  v
    #
    #

    # ensures is first layer but cannot guarantee the order setup is applied
    app.middlewares.insert(
        0,
        middleware_factory(
            app_name,
            enter_middleware_cb=enter_middleware_cb,
            exit_middleware_cb=exit_middleware_cb,
        ),
    )

    app.router.add_get("/metrics", metrics_handler)

    return True
