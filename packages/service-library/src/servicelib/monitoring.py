"""

    UNDER DEVELOPMENT for issue #784

    Based on https://github.com/amitsaha/aiohttp-prometheus

    Clients:
    - https://github.com/prometheus/client_python
    - TODO: see https://github.com/claws/aioprometheus
"""

import prometheus_client
from aiohttp import web
from prometheus_client import Counter, Gauge, Histogram, CONTENT_TYPE_LATEST
import time


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


def setup_monitoring(app, app_name):

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

    app.middlewares.insert(0, middleware_factory(app_name))

    # FIXME: this in the front-end has to be protected!
    app.router.add_get("/metrics", metrics)
