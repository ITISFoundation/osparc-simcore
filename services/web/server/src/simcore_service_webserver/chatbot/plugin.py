"""tags management subsystem"""

import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ..products.plugin import setup_products
from ._client import setup_chatbot_rest_client

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CHATBOT",
    logger=_logger,
)
def setup_chatbot(app: web.Application):
    setup_products(app)
    app.on_startup.append(setup_chatbot_rest_client)
