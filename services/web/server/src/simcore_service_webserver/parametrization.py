""" parametrization app module setup

    - Project parametrization
    - Project snapshots

"""
import logging

from aiohttp import web
from servicelib.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)

from . import parametrization_api_handlers
from .constants import APP_SETTINGS_KEY
from .settings import ApplicationSettings

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.projects"],
    logger=log,
)
def setup(app: web.Application):

    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    if not settings.WEBSERVER_DEV_FEATURES_ENABLED:
        raise SkipModuleSetup(reason="Development feature")

    app.add_routes(parametrization_api_handlers.routes)
