""" director subsystem

    Provides access to the director backend service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .settings import get_plugin_settings

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.director",
    ModuleCategory.ADDON,
    depends=[],
    logger=logger,
)
def setup_director(app: web.Application):
    get_plugin_settings(app)
    # TODO: init some client
