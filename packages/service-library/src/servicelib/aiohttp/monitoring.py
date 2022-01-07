""" Enables monitoring of some quantities needed for diagnostics

"""

import asyncio
import logging
import time
from typing import List, Optional

import prometheus_client
from aiohttp import web
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    GCCollector,
    PlatformCollector,
    ProcessCollector,
)
from prometheus_client.registry import CollectorRegistry
from servicelib.aiohttp.typing_extension import Handler

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


kSTART_TIME = f"{__name__}.start_time"
kREQUEST_COUNT = f"{__name__}.request_count"
kCANCEL_COUNT = f"{__name__}.cancel_count"

kCOLLECTOR_REGISTRY = f"{__name__}.collector_registry"
kPROCESS_COLLECTOR = f"{__name__}.collector_process"
kPLATFORM_COLLECTOR = f"{__name__}.collector_platform"
kGC_COLLECTOR = f"{__name__}.collector_gc"


def get_collector_registry(app: web.Application) -> CollectorRegistry:
    return app[kCOLLECTOR_REGISTRY]


async def metrics_handler(request: web.Request):
    registry = get_collector_registry(request.app)

    # NOTE: Cannot use ProcessPoolExecutor because registry is not pickable
    result = await request.loop.run_in_executor(
        None, prometheus_client.generate_latest, registry
    )
    response = web.Response(body=result)
    response.content_type = CONTENT_TYPE_LATEST
    return response


def middleware_factory(app_name: str, excluded_paths: Optional[List[str]] = None):
    if not excluded_paths:
        excluded_paths = []

    @web.middleware
    async def middleware_handler(request: web.Request, handler: Handler):
        # See https://prometheus.io/docs/concepts/metric_types

        log_exception = None
        if request.rel_url.path in excluded_paths:
            return await handler(request)

        resp: web.StreamResponse = web.HTTPInternalServerError(
            reason="Unexpected exception"
        )
        try:
            log.debug("ENTERING monitoring middleware for %s", f"{request=}")
            request[kSTART_TIME] = time.time()

            resp = await handler(request)

            assert isinstance(  # nosec
                resp, web.StreamResponse
            ), "Forgot envelope middleware?"

            log.debug(
                "EXITING monitoring middleware for %s with %s",
                f"{request=}",
                f"{resp=}",
            )
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
            resp_time_secs: float = time.time() - request[kSTART_TIME]

            # prometheus probes
            request.app[kREQUEST_COUNT].labels(
                app_name,
                request.method,
                request.match_info.route.resource.canonical
                if request.match_info.route.resource
                else "undef",
                resp.status,
            ).inc()

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
    middleware_handler.__middleware_name__ = __name__  # SEE check_outermost_middleware

    return middleware_handler


def setup_monitoring(app: web.Application, app_name: str):
    # app-scope registry
    app[kCOLLECTOR_REGISTRY] = reg = CollectorRegistry(auto_describe=True)
    app[kPROCESS_COLLECTOR] = ProcessCollector(registry=reg)
    app[kPLATFORM_COLLECTOR] = PlatformCollector(registry=reg)
    app[kGC_COLLECTOR] = GCCollector(registry=reg)

    # Total number of requests processed
    app[kREQUEST_COUNT] = Counter(
        name="http_requests_total",
        documentation="Total Request Count",
        labelnames=["app_name", "method", "endpoint", "http_status"],
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
    app.middlewares.insert(0, middleware_factory(app_name))

    app.router.add_get("/metrics", metrics_handler)

    return True
