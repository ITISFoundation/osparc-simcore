""" clusters app module setup

    Allows a user to manage clusters depending on user group(s) access rights:
        - create, modify, delete clusters
        - monitor clusters
        - send computational jobs to clusters

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)

from ..application_settings import ApplicationSettings
from ..constants import APP_SETTINGS_KEY
from . import handlers

log = logging.getLogger(__file__)


@app_module_setup(
    "simcore_service_webserver.clusters",
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.groups"],
    logger=log,
)
def setup_clusters(app: web.Application):
    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    if not settings.WEBSERVER_DEV_FEATURES_ENABLED:
        raise SkipModuleSetup(reason="Development feature")

    app.add_routes(handlers.routes)


__all__ = ["setup_clusters"]
