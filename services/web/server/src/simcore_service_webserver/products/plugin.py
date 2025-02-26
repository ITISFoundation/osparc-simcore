"""
This framework can serve different variants of the front-end client denoted 'products'

A product can be customized using settings defined in the backend (see products pg table).
Some of these are also transmitted to the front-end client via statics (see statis_settings.py)

At every request to this service API, a middleware discovers which product is the requester and sets the appropriate product context

"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.db"],
    settings_name="WEBSERVER_PRODUCTS",
    logger=_logger,
)
def setup_products(app: web.Application):
    #
    # NOTE: internal import speeds up booting app
    # specially if this plugin is not set up to be loaded
    #
    from ..constants import APP_SETTINGS_KEY
    from ..rabbitmq import setup_rabbitmq
    from . import _rest, _rpc, _web_events, _web_middlewares

    assert app[APP_SETTINGS_KEY].WEBSERVER_PRODUCTS is True  # nosec

    # set middlewares
    app.middlewares.append(_web_middlewares.discover_product_middleware)

    # setup rest
    app.router.add_routes(_rest.routes)

    # setup rpc
    setup_rabbitmq(app)
    if app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(_rpc.register_rpc_routes_on_startup)

    # setup events
    app.on_startup.append(
        # NOTE: must go BEFORE load_products_on_startup
        _web_events.auto_create_products_groups
    )
    app.on_startup.append(_web_events.load_products_on_startup)
    app.cleanup_ctx.append(_web_events.setup_product_templates)
