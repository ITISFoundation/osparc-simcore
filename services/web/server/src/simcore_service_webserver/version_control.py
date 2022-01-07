""" An add-on on projects module

    Adds version control to projects

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import version_control_handlers
from .application_settings import ApplicationSettings
from .constants import APP_SETTINGS_KEY

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=[
        "simcore_service_webserver.projects",
    ],
    logger=log,
)
def setup_version_control(app: web.Application):

    app.add_routes(version_control_handlers.routes)
