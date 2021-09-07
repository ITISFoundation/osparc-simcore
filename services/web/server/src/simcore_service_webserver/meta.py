""" Meta-models app module setup

    Extend project's business logic by adding two new concepts, namely
        - checkpoints
        - parametrizations


"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)

from . import meta_api_handlers
from .constants import APP_SETTINGS_KEY
from .settings import ApplicationSettings

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.projects"],
    logger=log,
)
def setup_meta(app: web.Application):

    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    if not settings.WEBSERVER_DEV_FEATURES_ENABLED:
        raise SkipModuleSetup(reason="Development feature")

    # TODO: validate routes against OAS
    app.add_routes(meta_api_handlers.routes)
