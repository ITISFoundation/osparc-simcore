""" checkpoints (and parametrization) app module setup

    Extend project's business logic by adding two new concepts, namely
        - project snapshots and
        - parametrizations

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)

from . import repos_handlers
from .constants import APP_SETTINGS_KEY
from .settings import ApplicationSettings

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.projects"],
    logger=log,
)
def setup_repos(app: web.Application):

    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    if not settings.WEBSERVER_DEV_FEATURES_ENABLED:
        raise SkipModuleSetup(reason="Development feature")

    # TODO: validate routes against OAS
    app.add_routes(repos_handlers.routes)
