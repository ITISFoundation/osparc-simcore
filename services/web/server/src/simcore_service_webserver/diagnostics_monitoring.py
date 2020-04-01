""" Enables monitoring of some quantities needed for diagnostics

"""
import logging
import time
from typing import Coroutine

from aiohttp import web
from prometheus_client import Counter, Gauge, Histogram

from servicelib.monitoring import metrics_handler

log = logging.getLogger(__name__)


START_TIME = f"{__name__}.start_time"
REQUEST_IN_PROGRESS = f"{__name__}.request_in_progress"
REQUEST_LATENCY = f"{__name__}.request_latency"
REQUEST_COUNT = f"{__name__}.request_count"
CANCEL_COUNT = f"{__name__}.cancel_count"

# SETUP ----

def middleware_factory(app_name: str) -> Coroutine:
    @web.middleware
    async def middleware_handler(request: web.Request, handler):
        try:
            request[START_TIME] = time.time()
            request.app[REQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).inc()

            resp = await handler(request)
            exception_name = None

        except web.HTTPException as exc:
            # Transforms exception into response object
            resp = exc
            exception_name = None

        except Exception as exc:  # pylint: disable=broad-except
            # Unhandled exceptions transformed into status 500
            # NOTE: Prevents issue #1025
            resp = web.HTTPInternalServerError(reason=str(exc))
            exception_name = exc.__class__.__name__

        finally:
            resp_time = time.time() - request[START_TIME]

            request.app[REQUEST_LATENCY].labels(app_name, request.path).observe(
                resp_time
            )
            request.app[REQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).dec()

            request.app[REQUEST_COUNT].labels(
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
                    resp_time,
                    resp.status,
                )

        return resp

    middleware_handler.__middleware_name__ = f"{__name__}.{app_name}"
    return middleware_handler



def setup_monitoring(app: web.Application):
    # NOTE: prometheus_client registers metrics in **globals**.
    # Therefore tests might fail when fixtures get re-created

    # Total number of requests processed
    app[REQUEST_COUNT] = Counter(
        name="http_requests_total",
        documentation="Total Request Count",
        labelnames=["app_name", "method", "endpoint", "http_status", "exception"],
    )

    # Latency of a request in seconds
    app[REQUEST_LATENCY] = Histogram(
        name="http_request_latency_seconds",
        documentation="Request latency",
        labelnames=["app_name", "endpoint"],
    )

    # Number of requests in progress
    app[REQUEST_IN_PROGRESS] = Gauge(
        name="http_requests_in_progress_total",
        documentation="Requests in progress",
        labelnames=["app_name", "endpoint", "method"],
    )

    # ensures is first layer but cannot guarantee the order setup is applied
    app.middlewares.insert(0, middleware_factory("simcore_service_webserver"))

    # TODO: in production, it should only be accessible to backend services
    app.router.add_get("/metrics", metrics_handler)

    return True


# UTILITIES ----
from typing import Type

def get_exception_total_count(app: web.Application, exception_cls: Type[Exception]) -> int:
    counter: Counter =  app[REQUEST_COUNT]

    raise NotImplementedError()
    # exception_cls.__name__

    total_count = 0
    for metric in counter.collect():

        for sample in metric.samples:
            if sample.name.endswith("_total"):
                total_count += sample.value
    return total_count