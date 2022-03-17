""" director subsystem

    Provides access to the director backend service
"""

import logging
import warnings

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .settings import get_plugin_settings

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.director",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DIRECTOR",
    depends=[],
    logger=logger,
)
def setup_director(app: web.Application):
    warnings.warn(
        f"{__name__} plugin is deprecated, use director-v2 plugin instead",
        DeprecationWarning,
    )
    get_plugin_settings(app)
