"""
    Plugin to interact with the 'payments' service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from simcore_service_webserver.rabbitmq import setup_rabbitmq

from ..constants import APP_SETTINGS_KEY
from ..db.plugin import setup_db
from ..products.plugin import setup_products
from ..users.plugin import setup_users
from . import _events, _rpc_invoice
from ._tasks import create_background_task_to_fake_payment_completion

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_PAYMENTS",
    logger=_logger,
)
def setup_payments(app: web.Application):
    settings = app[APP_SETTINGS_KEY].WEBSERVER_PAYMENTS

    setup_db(app)
    setup_products(app)

    app.on_startup.append(_events.validate_prices_in_product_settings_on_startup)

    setup_users(app)

    # rpc api
    setup_rabbitmq(app)
    if app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(_rpc_invoice.register_rpc_routes_on_startup)

    if settings.PAYMENTS_FAKE_COMPLETION:
        _logger.warning(
            "Added faker payment completion. ONLY FOR front-end TESTING PURPOSES"
        )
        app.cleanup_ctx.append(
            create_background_task_to_fake_payment_completion(wait_period_s=3)
        )
