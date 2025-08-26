"""
This framework can serve different variants of the front-end client denoted 'products'

A product can be customized using settings defined in the backend (see products pg table).
Some of these are also transmitted to the front-end client via statics (see statis_settings.py)

At every request to this service API, a middleware discovers which product is the requester and sets the appropriate product context

"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import (
    ModuleCategory,
    app_module_setup,
    ensure_single_setup,
)

_logger = logging.getLogger(__name__)


@ensure_single_setup(f"{__name__}.without_rpc", logger=_logger)
def setup_products_without_rpc(app: web.Application):
    #
    # NOTE: internal import speeds up booting app
    # specially if this plugin is not set up to be loaded
    #
    from ..constants import APP_SETTINGS_KEY
    from . import _web_events, _web_middlewares
    from ._controller import rest

    assert app[APP_SETTINGS_KEY].WEBSERVER_PRODUCTS is True  # nosec

    # rest API
    app.middlewares.append(_web_middlewares.discover_product_middleware)
    app.router.add_routes(rest.routes)

    _web_events.setup_web_events(app)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.db"],
    settings_name="WEBSERVER_PRODUCTS",
    logger=_logger,
)
def setup_products(app: web.Application):
    from ._controller import rpc

    setup_products_without_rpc(app)

    # rpc API (optional)
    rpc.setup_rpc(app)
