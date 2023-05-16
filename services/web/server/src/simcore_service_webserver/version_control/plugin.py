""" An add-on on projects module

    Adds version control to projects

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from . import _rest_handlers

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_VERSION_CONTROL",
    depends=[
        "simcore_service_webserver.projects",
    ],
    logger=log,
)
def setup_version_control(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_VERSION_CONTROL  # nosec

    app.add_routes(_rest_handlers.routes)
