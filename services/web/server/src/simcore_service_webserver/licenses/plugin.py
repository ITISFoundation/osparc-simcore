""" tags management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..rabbitmq import setup_rabbitmq
from . import (
    _licensed_items_checkouts_rest,
    _licensed_items_purchases_rest,
    _licensed_items_rest,
    _rpc,
)

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_LICENSES",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_licenses(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_LICENSES  # nosec

    # routes
    app.router.add_routes(_licensed_items_rest.routes)
    app.router.add_routes(_licensed_items_purchases_rest.routes)
    app.router.add_routes(_licensed_items_checkouts_rest.routes)

    setup_rabbitmq(app)
    if app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(_rpc.register_rpc_routes_on_startup)
