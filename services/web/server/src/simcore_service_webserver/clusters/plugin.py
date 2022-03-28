""" clusters app module setup

    Allows a user to manage clusters depending on user group(s) access rights:
        - create, modify, delete clusters
        - monitor clusters
        - send computational jobs to clusters

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .. import director_v2
from .._constants import APP_SETTINGS_KEY
from . import handlers

log = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.clusters",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CLUSTERS",
    logger=log,
)
def setup_clusters(app: web.Application):
    director_v2.setup_director_v2(app)
    assert app[APP_SETTINGS_KEY].WEBSERVER_CLUSTERS  # nosec

    app.add_routes(handlers.routes)


__all__ = ["setup_clusters"]
