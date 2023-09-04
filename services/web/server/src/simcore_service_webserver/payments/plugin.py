"""
    Plugin to interact with the 'payments' service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from ..db.plugin import setup_db
from ._client import payments_service_api_cleanup_ctx
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

    app.cleanup_ctx.append(payments_service_api_cleanup_ctx)

    if settings.PAYMENT_FAKE_COMPLETION:
        _logger.warning(
            "Added faker payment completion. ONLY FOR front-end TESTING PURPOSES"
        )
        app.cleanup_ctx.append(
            create_background_task_to_fake_payment_completion(wait_period_s=3)
        )
