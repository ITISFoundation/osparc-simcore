"""
Plugin to broadcast announcements to all front-end users
"""

import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..products.plugin import setup_products
from ..redis import setup_redis
from . import _handlers

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_ANNOUNCEMENTS",
    logger=_logger,
)
def setup_announcements(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_ANNOUNCEMENTS  # nosec

    setup_products(app)
    setup_redis(app)

    app.router.add_routes(_handlers.routes)
