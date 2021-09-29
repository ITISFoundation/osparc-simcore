""" Version control app module

    Manages version control of studies, both the project document and the associated data

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)

from . import version_control_handlers
from .constants import APP_SETTINGS_KEY
from .settings import ApplicationSettings

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=[
        "simcore_service_webserver.projects",
        "simcore_service_webserver.version_control",
    ],
    logger=log,
)
def setup_meta(app: web.Application):

    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    if not settings.WEBSERVER_DEV_FEATURES_ENABLED:
        raise SkipModuleSetup(reason="Development feature")

    app.add_routes(version_control_handlers.routes)
