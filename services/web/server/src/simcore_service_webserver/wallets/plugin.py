""" tags management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..payments.plugin import setup_payments
from . import _groups_handlers, _handlers, _payments_handlers

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_WALLETS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_wallets(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_WALLETS  # nosec

    app.router.add_routes(_handlers.routes)
    app.router.add_routes(_groups_handlers.routes)

    setup_payments(app)
    if app[APP_SETTINGS_KEY].WEBSERVER_PAYMENTS:
        app.router.add_routes(_payments_handlers.routes)
