""" Enables monitoring of some quantities needed for diagnostics

"""
import logging
import time
from asyncio.exceptions import CancelledError

import prometheus_client
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter
from prometheus_client.registry import CollectorRegistry
from servicelib.aiohttp.monitor_services import add_instrumentation
from servicelib.aiohttp.typing_extension import Handler, Middleware

from .diagnostics_core import DelayWindowProbe, is_sensing_enabled, kLATENCY_PROBE

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

# TODO: the endpoint label on the http_requests_total Counter is a candidate to be removed. as endpoints also contain all kind of UUIDs

kSTART_TIME = f"{__name__}.start_time"
kREQUEST_COUNT = f"{__name__}.request_count"
kCANCEL_COUNT = f"{__name__}.cancel_count"

kCOLLECTOR_REGISTRY = f"{__name__}.collector_registry"


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


def middleware_factory(app_name: str) -> Middleware:
    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):
        if request.rel_url.path == "/socket.io/":
            return await handler(request)

        log_exception = None
        resp: web.StreamResponse = web.HTTPInternalServerError(
            reason="Unexpected exception"
        )

        try:
            request[kSTART_TIME] = time.time()

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

        except Exception as exc:  # pylint: disable=broad-except
            # Transforms unhandled exceptions into responses with status 500
            # NOTE: Prevents issue #1025
            resp = web.HTTPInternalServerError(reason=str(exc))
            resp.__cause__ = exc
            log_exception = exc

        except CancelledError as exc:
            # Mostly for logging
            resp = web.HTTPInternalServerError(reason=str(exc))
            log_exception = exc
            raise

        finally:
            resp_time_secs: float = time.time() - request[kSTART_TIME]

            exc_name = ""
            if log_exception:
                exc_name: str = log_exception.__class__.__name__

            # Probes request latency
            # NOTE: sockets connection is long
            # FIXME: tmp by hand, add filters directly in probe
            if not str(request.path).startswith("/socket.io") and is_sensing_enabled(
                request.app
            ):
                request.app[kLATENCY_PROBE].observe(resp_time_secs)

            # prometheus probes
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

    add_instrumentation(app, get_collector_registry(app), "simcore_service_webserver")

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
