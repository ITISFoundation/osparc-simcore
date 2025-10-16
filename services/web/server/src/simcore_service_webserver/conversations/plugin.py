"""tags management subsystem"""

import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..chatbot.plugin import setup_chatbot
from ..fogbugz.plugin import setup_fogbugz
from ._controller import _conversations_messages_rest, _conversations_rest

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_CONVERSATIONS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_conversations(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_CONVERSATIONS  # nosec

    setup_fogbugz(app)
    setup_chatbot(app)

    app.router.add_routes(_conversations_rest.routes)
    app.router.add_routes(_conversations_messages_rest.routes)
