""" Subsystem to communicate with catalog service

"""
import logging

from aiohttp import web
from pint import UnitRegistry
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _handlers

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CATALOG",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_catalog(app: web.Application):
    # ensures routes are names that corresponds to function names
    assert all(  # nosec
        route_def.kwargs["name"] == route_def.handler.__name__
        for route_def in _handlers.routes
    )

    app.add_routes(_handlers.routes)

    # prepares units registry
    app[UnitRegistry.__name__] = UnitRegistry()
