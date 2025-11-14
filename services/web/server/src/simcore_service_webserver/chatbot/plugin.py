import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ..products.plugin import setup_products
from ..rabbitmq import setup_rabbitmq
from ._client import setup_chatbot_rest_client
from ._process_chatbot_trigger_service import on_cleanup_ctx_rabbitmq_consumer

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CHATBOT",
    logger=_logger,
)
def setup_chatbot(app: web.Application):
    setup_products(app)
    setup_rabbitmq(app)
    app.on_startup.append(setup_chatbot_rest_client)
    app.cleanup_ctx.append(on_cleanup_ctx_rabbitmq_consumer)
