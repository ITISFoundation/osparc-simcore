""" Enables monitoring of some quantities needed for diagnostics

"""
import logging
import time
from typing import Coroutine

import prometheus_client
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram
from prometheus_client.registry import CollectorRegistry

from .diagnostics_core import DelayWindowProbe, kLATENCY_PROBE

log = logging.getLogger(__name__)

kSTART_TIME = f"{__name__}.start_time"
kREQUEST_IN_PROGRESS = f"{__name__}.request_in_progress"
kREQUEST_LATENCY = f"{__name__}.request_latency"
kREQUEST_COUNT = f"{__name__}.request_count"
kCANCEL_COUNT = f"{__name__}.cancel_count"

kCOLLECTOR_REGISTRY = f"{__name__}.collector_registry"


async def metrics_handler(request: web.Request):
    # TODO: prometheus_client.generate_latest blocking! -> Consider https://github.com/claws/aioprometheus
    reg = request.app[kCOLLECTOR_REGISTRY]
    resp = web.Response(body=prometheus_client.generate_latest(registry=reg))
    resp.content_type = CONTENT_TYPE_LATEST
    return resp


def middleware_factory(app_name: str) -> Coroutine:
    @web.middleware
    async def _middleware_handler(request: web.Request, handler):
        try:
            request[kSTART_TIME] = time.time()
            request.app[kREQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).inc()

            resp = await handler(request)
            log_exception = None

            assert isinstance(
                resp, web.StreamResponse
            ), "Forgot envelope middleware?"  # nsec

        except web.HTTPServerError as exc:
            # Transforms exception into response object and log exception
            resp = exc
            log_exception = exc

        except web.HTTPException as exc:
            # Transforms non-HTTPServerError exceptions into response object
            resp = exc
            log_exception = None

        except Exception as exc:  # pylint: disable=broad-except
            # Transforms unhandled exceptions into responses with status 500
            # NOTE: Prevents issue #1025
            resp = web.HTTPInternalServerError(reason=str(exc))
            log_exception = exc

        finally:
            resp_time_secs: float = time.time() - request[kSTART_TIME]

            exc_name = ""
            if log_exception:
                exc_name: str = log_exception.__class__.__name__

            # Probes request latency
            # NOTE: sockets connection is long
            # FIXME: tmp by hand, add filters directly in probe
            if not str(request.path).startswith("/socket.io"):
                request.app[kLATENCY_PROBE].observe(resp_time_secs)

            # prometheus probes
            request.app[kREQUEST_LATENCY].labels(app_name, request.path).observe(
                resp_time_secs
            )

            request.app[kREQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).dec()

            request.app[kREQUEST_COUNT].labels(
                app_name, request.method, request.path, resp.status, exc_name
            ).inc()

            if log_exception:
                log.error(
                    'Unexpected server error "%s" from access: %s "%s %s" done in %3.2f secs. Responding with status %s',
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
    _middleware_handler.__middleware_name__ = f"{__name__}.monitor_{app_name}"

    return _middleware_handler


def setup_monitoring(app: web.Application):
    # app-scope registry
    app[kCOLLECTOR_REGISTRY] = reg = CollectorRegistry(auto_describe=True)

    # Total number of requests processed
    app[kREQUEST_COUNT] = Counter(
        name="http_requests_total",
        documentation="Total Request Count",
        labelnames=["app_name", "method", "endpoint", "http_status", "exception"],
        registry=reg,
    )

    # Latency of a request in seconds
    app[kREQUEST_LATENCY] = Histogram(
        name="http_request_latency_seconds",
        documentation="Request latency",
        labelnames=["app_name", "endpoint"],
        registry=reg,
    )

    # Number of requests in progress
    app[kREQUEST_IN_PROGRESS] = Gauge(
        name="http_requests_in_progress_total",
        documentation="Requests in progress",
        labelnames=["app_name", "endpoint", "method"],
        registry=reg,
    )

    # on-the fly stats
    app[kLATENCY_PROBE] = DelayWindowProbe()

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
    app.middlewares.insert(0, middleware_factory("simcore_service_webserver"))

    # TODO: in production, it should only be accessible to backend services
    app.router.add_get("/metrics", metrics_handler)

    return True


def get_collector_registry(app: web.Application) -> CollectorRegistry:
    return app[kCOLLECTOR_REGISTRY]
