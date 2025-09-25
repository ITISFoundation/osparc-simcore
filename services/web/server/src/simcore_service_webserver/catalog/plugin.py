"""Subsystem to communicate with catalog service"""

import logging
from typing import Final

from aiohttp import web
from pint import UnitRegistry

from ..application_setup import ModuleCategory, app_setup_func
from . import _controller_rest
from ._application_keys import UNIT_REGISTRY_APPKEY

_logger = logging.getLogger(__name__)

CATALOG_CLIENT_APPKEY: Final = web.AppKey("APP_CATALOG_CLIENT_KEY", object)


@app_setup_func(
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

    # prepares units registry
    app[UNIT_REGISTRY_APPKEY] = UnitRegistry()
