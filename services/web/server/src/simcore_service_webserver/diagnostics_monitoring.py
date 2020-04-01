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
    # TODO: prometheus_client.generate_latest blocking! no asyhc solutin?
    reg = request.app[kCOLLECTOR_REGISTRY]
    resp = web.Response(body=prometheus_client.generate_latest(registry=reg))
    resp.content_type = CONTENT_TYPE_LATEST
    return resp


def middleware_factory(app_name: str) -> Coroutine:
    @web.middleware
    async def middleware_handler(request: web.Request, handler):
        try:
            request[kSTART_TIME] = time.time()
            request.app[kREQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).inc()

            resp = await handler(request)
            unhandled_exception = None

        except web.HTTPException as exc:
            # Transforms exception into response object
            resp = exc
            unhandled_exception = None

        except Exception as exc:  # pylint: disable=broad-except
            # Transforms unhandled exceptions into responses with status 500
            # NOTE: Prevents issue #1025
            resp = web.HTTPInternalServerError(reason=str(exc))
            unhandled_exception = exc

        finally:
            resp_time_secs: float = time.time() - request[kSTART_TIME]

            request.app[kREQUEST_LATENCY].labels(app_name, request.path).observe(
                resp_time_secs
            )

            request.app[kREQUEST_IN_PROGRESS].labels(
                app_name, request.path, request.method
            ).dec()

            exc_name: str = unhandled_exception.__class__.__name__ if unhandled_exception else ""

            request.app[kREQUEST_COUNT].labels(
                app_name, request.method, request.path, resp.status, exc_name
            ).inc()

            if unhandled_exception:
                # NOTE: all access to API (i.e. and not other paths as /socket, /x, etc)
                # shall return web.HTTPErrors since processed by error_middleware_factory
                log.exception(
                    'Unexpected server error "%s" from access: %s "%s %s" done in %3.2f secs. Responding with status %s',
                    type(unhandled_exception),
                    request.remote,
                    request.method,
                    request.path,
                    resp_time_secs,
                    resp.status,
                )

            # Probes for on-the-fly stats ---
            # NOTE: might implement in the future some kind of statistical accumulator
            # to perform incremental calculations on the fly

            # Probes request latency
            request.app[kLATENCY_PROBE].observe(resp_time_secs)

        return resp

    middleware_handler.__middleware_name__ = f"{__name__}.{app_name}"
    return middleware_handler


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
    assert len(app.middlewares) >= 1  # nosec
    app.middlewares.append(middleware_factory("simcore_service_webserver"))

    # TODO: in production, it should only be accessible to backend services
    app.router.add_get("/metrics", metrics_handler)

    return True
