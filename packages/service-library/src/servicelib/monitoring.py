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


# https://prometheus.io/docs/concepts/metric_types/#counter

def middleware_factory(app_name):
    @web.middleware
    async def middleware_handler(request, handler):
        try:
            request['start_time'] = time.time()
            request.app['REQUEST_IN_PROGRESS'].labels(
                app_name, request.path, request.method).inc()

            resp = await handler(request)

        except web.HTTPException as ee:
            # Captures raised reponses (success/failures accounted with resp.status)
            resp = ee
            raise
        except Exception: #pylint: disable=broad-except
            # Prevents issue #1025. FIXME: why middleware below is not non-http exception safe?
            log.exception("Unexpected exception. \
                Error middleware below should only raise web.HTTPExceptions.")
            resp = web.HTTPInternalServerError()
            raise
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
    return middleware_handler

async def metrics(_request):
    # TODO: NOT async!
    # prometheus_client access to a singleton registry!
    resp = web.Response(body=prometheus_client.generate_latest())
    resp.content_type = CONTENT_TYPE_LATEST
    return resp

def setup_monitoring(app: web.Application, app_name: str):

    # NOTE: prometheus_client registers metrics in globals
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
