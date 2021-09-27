import logging
from typing import Tuple

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.tracing import schema, setup_tracing

from ._meta import APP_NAME

CONFIG_SECTION_NAME = "tracing"

log = logging.getLogger(__name__)


@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup_app_tracing(app: web.Application):
    config = app[APP_CONFIG_KEY]
    host = config["main"]["host"]
    port = config["main"]["port"]
    return setup_tracing(
        app, "simcore_service_webserver", host, port, config["tracing"]
    )


__all__: Tuple[str, ...] = ("schema", "setup_app_tracing")
