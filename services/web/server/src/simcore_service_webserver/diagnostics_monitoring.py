""" Enables monitoring of some quantities needed for diagnostics

"""
import logging

# SETUP ----
import statistics
import time
from typing import Coroutine

from aiohttp import web
from prometheus_client import Counter, Gauge, Histogram

from servicelib.monitoring import metrics_handler

from .diagnostics_core import kLAST_REQUESTS_AVG_LATENCY

log = logging.getLogger(__name__)

# APP KEYS ---
kSTART_TIME = f"{__name__}.start_time"
kREQUEST_IN_PROGRESS = f"{__name__}.request_in_progress"
kREQUEST_LATENCY = f"{__name__}.request_latency"
kREQUEST_COUNT = f"{__name__}.request_count"
kCANCEL_COUNT = f"{__name__}.cancel_count"

kLAST_REQUESTS_LATENCY = f"{__name__}.last_requests_latency"
LAST_REQUESTS_WINDOW = 100


def middleware_factory(app_name: str) -> Coroutine:
    @web.middleware
    async def middleware_handler(request: web.Request, handler):
        try:
            request[kSTART_TIME] = time.time()
            request.app[kREQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).inc()

            resp = await handler(request)
            exception_name = None

        except web.HTTPException as exc:
            # Transforms exception into response object
            resp = exc
            exception_name = None

        except Exception as exc:  # pylint: disable=broad-except
            # Transforms unhandled exceptions into responses with status 500
            # NOTE: Prevents issue #1025
            resp = web.HTTPInternalServerError(reason=str(exc))
            exception_name = exc.__class__.__name__

        finally:
            resp_time_secs: float = time.time() - request[kSTART_TIME]

            request.app[kREQUEST_LATENCY].labels(app_name, request.path).observe(
                resp_time_secs
            )

            request.app[kREQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).dec()

            request.app[kREQUEST_COUNT].labels(
                app_name, request.method, request.path, resp.status, exception_name
            ).inc()

            if exception_name:
                # NOTE: all access to API (i.e. and not other paths as /socket, /x, etc)
                # shall return web.HTTPErrors since processed by error_middleware_factory
                log.exception(
                    'Unexpected server error "%s" from access: %s "%s %s" done in %3.2f secs. Responding with status %s',
                    type(exc),
                    request.remote,
                    request.method,
                    request.path,
                    resp_time_secs,
                    resp.status,
                )

            # On-the-fly stats ---
            # NOTE: might implement in the future some kind of statistical accumulator
            # to perform incremental calculations on the fly

            # Mean latency of the last N request slower than 1 sec
            if resp_time_secs > 1.0:
                fifo = request.app[kLAST_REQUESTS_LATENCY]
                fifo.append(resp_time_secs)
                if len(fifo) > LAST_REQUESTS_WINDOW:
                    fifo.pop(0)
                request.app[kLAST_REQUESTS_AVG_LATENCY] = statistics.mean(fifo)

        return resp

    middleware_handler.__middleware_name__ = f"{__name__}.{app_name}"
    return middleware_handler


def setup_monitoring(app: web.Application):
    # NOTE: prometheus_client registers metrics in **globals**.
    # Therefore tests might fail when fixtures get re-created

    # Total number of requests processed
    app[kREQUEST_COUNT] = Counter(
        name="http_requests_total",
        documentation="Total Request Count",
        labelnames=["app_name", "method", "endpoint", "http_status", "exception"],
    )

    # Latency of a request in seconds
    app[kREQUEST_LATENCY] = Histogram(
        name="http_request_latency_seconds",
        documentation="Request latency",
        labelnames=["app_name", "endpoint"],
    )

    # Number of requests in progress
    app[kREQUEST_IN_PROGRESS] = Gauge(
        name="http_requests_in_progress_total",
        documentation="Requests in progress",
        labelnames=["app_name", "endpoint", "method"],
    )

    # on-the fly stats
    app[kLAST_REQUESTS_LATENCY] = []

    # ensures is first layer but cannot guarantee the order setup is applied
    app.middlewares.insert(0, middleware_factory("simcore_service_webserver"))

    # TODO: in production, it should only be accessible to backend services
    app.router.add_get("/metrics", metrics_handler)

    return True
