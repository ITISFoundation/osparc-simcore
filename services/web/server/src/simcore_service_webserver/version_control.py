""" An add-on on projects module

    Adds version control to projects

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    SkipModuleSetup,
    app_module_setup,
)

from . import version_control_handlers
from ._constants import APP_SETTINGS_KEY

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

    if not app[APP_SETTINGS_KEY].WEBSERVER_META_MODELING:
        raise SkipModuleSetup(
            reason="{__name__} plugin was explictly disabled in the app settings"
        )

    app.add_routes(version_control_handlers.routes)
