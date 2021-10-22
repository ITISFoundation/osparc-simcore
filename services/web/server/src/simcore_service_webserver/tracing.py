import logging

import trafaret as T
from aiohttp import web
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import setup_tracing

CONFIG_SECTION_NAME = "tracing"

log = logging.getLogger(__name__)


# TODO: deprecated by TracingSettings in https://github.com/ITISFoundation/osparc-simcore/pull/2376
# NOT used
schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.ToInt),
        T.Key("zipkin_endpoint", default="http://jaeger:9411"): T.String(),
    }
)


@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup_app_tracing(app: web.Application):

    # TODO: this should be part of app settings but
    # temporary here until https://github.com/ITISFoundation/osparc-simcore/pull/2376 is completed
    config = app[APP_CONFIG_KEY]
    host = config["main"]["host"]
    port = config["main"]["port"]
    cfg = config[CONFIG_SECTION_NAME]
    zipkin_endpoint = cfg["zipkin_endpoint"]
    assert cfg["enabled"]  # nosec
    return setup_tracing(
        app,
        service_name="simcore_service_webserver",
        host=host,
        port=port,
        jaeger_base_url=zipkin_endpoint,
        # TODO: skip all routes that are ouside vX ??
        skip_routes=None,
    )
