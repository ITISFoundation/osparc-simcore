"""

    UNDER DEVELOPMENT for issue #784 (see web/server/diagnostics_monitoring.py)

    Based on https://github.com/amitsaha/aiohttp-prometheus

    Clients:
    - https://github.com/prometheus/client_python
    - TODO: see https://github.com/claws/aioprometheus
"""

import asyncio
import logging
import time

import prometheus_client
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter

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


async def metrics_handler(_request: web.Request):
    # TODO: prometheus_client.generate_latest blocking! no asyhc solutin?
    # TODO: prometheus_client access to a singleton registry! can be instead created and pass to every metric wrapper
    resp = web.Response(body=prometheus_client.generate_latest())
    resp.content_type = CONTENT_TYPE_LATEST
    return resp


def middleware_factory(app_name):
    @web.middleware
    async def middleware_handler(request: web.Request, handler):
        # See https://prometheus.io/docs/concepts/metric_types
        resp = None
        try:
            log.debug("ENTERING monitoring middleware for %s", f"{request=}")
            request["start_time"] = time.time()

            resp = await handler(request)
            log.debug(
                "EXITING monitoring middleware for %s with %s",
                f"{request=}",
                f"{resp=}",
            )

        except web.HTTPException as exc:
            # Captures raised reponses (success/failures accounted with resp.status)
            resp = exc
            raise
        except asyncio.CancelledError as exc:
            # python 3.8 cancellederror is a subclass of BaseException and NOT Exception
            resp = web.HTTPRequestTimeout(reason=str(exc))
        except BaseException as exc:  # pylint: disable=broad-except
            # Prevents issue #1025.
            resp = web.HTTPInternalServerError(reason=str(exc))

            # NOTE: all access to API (i.e. and not other paths as /socket, /x, etc) shall return web.HTTPErrors since processed by error_middleware_factory
            log.exception(
                'Unexpected server error "%s" from access: %s "%s %s" done in %3.2f secs. Responding with status %s',
                type(exc),
                request.remote,
                request.method,
                request.path,
                time.time() - request["start_time"],
                resp.status,
            )

        finally:
            # metrics on the same request
            log.debug("REQUEST RESPONSE %s", f"{resp=}")
            if resp is not None:
                request.app["REQUEST_COUNT"].labels(
                    app_name, request.method, request.path, resp.status
                ).inc()

        return resp

    middleware_handler.__middleware_name__ = __name__  # SEE check_outermost_middleware
    return middleware_handler


async def check_outermost_middleware(
    app: web.Application, *, log_failure: bool = True
) -> bool:
    try:
        ok = app.middlewares[0].__middleware_name__ == __name__
    except (IndexError, AttributeError):
        ok = False

    if not ok and log_failure:

        def _view(m) -> str:
            try:
                return f"{m.__middleware_name__} [{m}]"
            except AttributeError:
                return str(m)

        log.critical(
            "Monitoring middleware expected in the outermost layer. "
            "Middleware stack: %s. "
            "TIP: Check setup order",
            [_view(m) for m in app.middlewares],
        )
    return ok


def setup_monitoring(app: web.Application, app_name: str):
    # NOTE: prometheus_client registers metrics in **globals**. Therefore
    # tests might fail when fixtures get re-created

    # Total number of requests processed
    app["REQUEST_COUNT"] = Counter(
        "http_requests_total",
        "Total Request Count",
        ["app_name", "method", "endpoint", "http_status"],
    )

    # ensures is first layer but cannot guarantee the order setup is applied
    app.middlewares.insert(0, middleware_factory(app_name))

    # FIXME: this in the front-end has to be protected!
    app.router.add_get("/metrics", metrics_handler)

    # Checks that middleware is in the outermost layer
    app.on_startup.append(check_outermost_middleware)

    return True
