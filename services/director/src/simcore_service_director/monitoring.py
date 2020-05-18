import prometheus_client
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client.registry import CollectorRegistry

from servicelib.monitor_services import (
    add_instrumentation as add_services_instrumentation,
)

from . import config

kCOLLECTOR_REGISTRY = f"{__name__}.collector_registry"


async def metrics_handler(_request: web.Request):
    # TODO: prometheus_client.generate_latest blocking! no asyhc solutin?
    # TODO: prometheus_client access to a singleton registry! can be instead created and pass to every metric wrapper
    resp = web.Response(body=prometheus_client.generate_latest())
    resp.content_type = CONTENT_TYPE_LATEST
    return resp


def setup_app_monitoring(app: web.Application, app_name: str) -> None:
    if not config.MONITORING_ENABLED:
        return
    # app-scope registry
    app[kCOLLECTOR_REGISTRY] = reg = CollectorRegistry(auto_describe=True)

    add_services_instrumentation(app, reg, app_name)

    # FIXME: this in the front-end has to be protected!
    app.router.add_get("/metrics", metrics_handler)
