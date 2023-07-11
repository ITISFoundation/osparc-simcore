"""
    Plugin to broadcast announcements to all front-end users
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from ..products.plugin import setup_products
from ..redis import setup_redis
from . import _handlers

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_ANNOUNCEMENTS",
    logger=_logger,
)
def setup_announcements(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_ANNOUNCEMENTS  # nosec

    setup_products(app)
    setup_redis(app)

    app.router.add_routes(_handlers.routes)
