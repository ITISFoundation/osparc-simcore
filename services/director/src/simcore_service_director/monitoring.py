import prometheus_client
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client.registry import CollectorRegistry

if servicelib.__version__ >= "1.0.0":
    from servicelib.aiohttp.monitor_services import (
        add_instrumentation as add_services_instrumentation,
    )
else:
    from servicelib.monitor_services import (
        add_instrumentation as add_services_instrumentation,
    )

from . import config

kCOLLECTOR_REGISTRY = f"{__name__}.collector_registry"


async def metrics_handler(request: web.Request):
    # TODO: prometheus_client.generate_latest blocking! -> Consider https://github.com/claws/aioprometheus
    reg = request.app[kCOLLECTOR_REGISTRY]
    resp = web.Response(body=prometheus_client.generate_latest(registry=reg))
    resp.content_type = CONTENT_TYPE_LATEST
    return resp


def setup_app_monitoring(app: web.Application, app_name: str) -> None:
    if not config.MONITORING_ENABLED:
        return
    # app-scope registry
    app[kCOLLECTOR_REGISTRY] = reg = CollectorRegistry(auto_describe=True)

    add_services_instrumentation(app, reg, app_name)

    app.router.add_get("/metrics", metrics_handler)
