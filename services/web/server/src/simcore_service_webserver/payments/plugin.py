"""
    Plugin to interact with the payments service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from ..db.plugin import setup_db
from ._client import payments_service_api_cleanup_ctx

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_PAYMENTS",
    logger=_logger,
)
def setup_payments(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_PAYMENTS  # nosec

    setup_db(app)

    app.cleanup_ctx.append(payments_service_api_cleanup_ctx)
