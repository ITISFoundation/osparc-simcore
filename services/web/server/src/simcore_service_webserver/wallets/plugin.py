"""tags management subsystem"""

import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..payments.plugin import setup_payments
from . import _groups_handlers, _handlers, _payments_handlers
from ._events import setup_wallets_events

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_WALLETS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_wallets(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_WALLETS  # nosec

    # routes
    app.router.add_routes(_handlers.routes)
    app.router.add_routes(_groups_handlers.routes)

    setup_payments(app)
    if app[APP_SETTINGS_APPKEY].WEBSERVER_PAYMENTS:
        app.router.add_routes(_payments_handlers.routes)

    # events
    setup_wallets_events(app)
