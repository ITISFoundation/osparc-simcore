"""Subsystem to communicate with catalog service"""

import logging

from aiohttp import web
from pint import UnitRegistry
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from . import _controller_rest, _controller_rest_tags_handlers

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
        route_def.kwargs["name"] == route_def.handler.__name__  # type: ignore[attr-defined] # route_def is a RouteDef not an Abstract
        for route_def in _controller_rest.routes
    )

    app.add_routes(_controller_rest.routes)
    app.add_routes(_controller_rest_tags_handlers.routes)

    # prepares units registry
    app[UnitRegistry.__name__] = UnitRegistry()
