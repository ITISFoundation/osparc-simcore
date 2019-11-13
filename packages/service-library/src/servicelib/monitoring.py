"""

    UNDER DEVELOPMENT for issue #784

    Based on https://github.com/amitsaha/aiohttp-prometheus

    Clients:
    - https://github.com/prometheus/client_python
    - TODO: see https://github.com/claws/aioprometheus
"""

import logging
import time

import prometheus_client
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram


log = logging.getLogger(__name__)


def middleware_factory(app_name):
    @web.middleware
    async def middleware_handler(request: web.Request, handler):
        # See https://prometheus.io/docs/concepts/metric_types
        try:
            request['start_time'] = time.time()
            request.app['REQUEST_IN_PROGRESS'].labels(
                app_name, request.path, request.method).inc()

            resp = await handler(request)

        except web.HTTPException as exc:
            # Captures raised reponses (success/failures accounted with resp.status)
            resp = exc
            raise
        except Exception as exc: #pylint: disable=broad-except
            # Prevents issue #1025.
            resp = web.HTTPInternalServerError(reason=str(exc))
            resp_time = time.time() - request['start_time']

            # NOTE: all access to API (i.e. and not other paths as /socket, /x, etc) shall return web.HTTPErrors since processed by error_middleware_factory
            log.exception('Unexpected server error "%s" from access: %s "%s %s" done in %3.2f secs. Responding with status %s',
                type(exc),
                request.remote, request.method, request.path,
                resp_time,
                resp.status
            )
        finally:
            # metrics on the same request
            resp_time = time.time() - request['start_time']
            request.app['REQUEST_LATENCY'].labels(
                app_name, request.path).observe(resp_time)

            request.app['REQUEST_IN_PROGRESS'].labels(
                app_name, request.path, request.method).dec()

            request.app['REQUEST_COUNT'].labels(
                app_name, request.method, request.path, resp.status).inc()

        return resp

    middleware_handler.__middleware_name__ = __name__
    return middleware_handler

async def metrics(_request):
    # TODO: NOT async!
    # prometheus_client access to a singleton registry!
    resp = web.Response(body=prometheus_client.generate_latest())
    resp.content_type = CONTENT_TYPE_LATEST
    return resp

async def check_outermost_middleware(app: web.Application):
    m = app.middlewares[0]
    ok = m and hasattr(m, "__middleware_name__") and m.__middleware_name__==__name__
    if not ok:
        # TODO: name all middleware and list middleware in log
        log.critical("Monitoring middleware expected in the outermost layer."
            "TIP: Check setup order")

def setup_monitoring(app: web.Application, app_name: str):
    # NOTE: prometheus_client registers metrics in **globals**. Therefore
    # tests might fail when fixtures get re-created

    # Total number of requests processed
    app['REQUEST_COUNT'] = Counter(
        'http_requests_total', 'Total Request Count',
        ['app_name', 'method', 'endpoint', 'http_status']
    )

    # Latency of a request in seconds
    app['REQUEST_LATENCY'] = Histogram(
        'http_request_latency_seconds', 'Request latency',
        ['app_name', 'endpoint']
    )

    # Number of requests in progress
    app['REQUEST_IN_PROGRESS']=Gauge(
        'http_requests_in_progress_total', 'Requests in progress',
        ['app_name', 'endpoint', 'method']
    )

    # ensures is first layer but cannot guarantee the order setup is applied
    app.middlewares.insert(0, middleware_factory(app_name))

    # FIXME: this in the front-end has to be protected!
    app.router.add_get("/metrics", metrics)

    # Checks that middleware is in the outermost layer
    app.on_startup.append(check_outermost_middleware)

    return True
