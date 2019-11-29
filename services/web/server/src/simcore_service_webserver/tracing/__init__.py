import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.tracing import setup_tracing
from servicelib.tracing import schema


CONFIG_SECTION_NAME = 'tracing'

log = logging.getLogger(__name__)

@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup(app: web.Application):
    config = app[APP_CONFIG_KEY]
    host=config["main"]["host"]
    port=config["main"]["port"]
    return setup_tracing(app, "simcore_service_webserver", host, port, config["tracing"])

# alias
setup_app_tracing = setup
tracing_section_name = CONFIG_SECTION_NAME
__all__ = (
    "setup_app_tracing",
    "schema",
    "tracing_section_name"
)
