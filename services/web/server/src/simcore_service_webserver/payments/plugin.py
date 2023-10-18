"""
    Plugin to interact with the 'payments' service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from simcore_service_webserver.rabbitmq import setup_rabbitmq

from .._constants import APP_SETTINGS_KEY
from ..db.plugin import setup_db
from ._client import rabbitmq_rpc_client_lifespan
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
    setup_rabbitmq(app)

    app.cleanup_ctx.append(rabbitmq_rpc_client_lifespan)

    # TODO: Remove partially fake payments?
    if settings.PAYMENTS_FAKE_COMPLETION:
        _logger.warning(
            "Added faker payment completion. ONLY FOR front-end TESTING PURPOSES"
        )
        app.cleanup_ctx.append(
            create_background_task_to_fake_payment_completion(wait_period_s=3)
        )
