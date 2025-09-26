"""tags management subsystem"""

import logging

from aiohttp import web

from ..application_setup import ModuleCategory, app_setup_func
from ..constants import APP_SETTINGS_KEY
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
    assert app[APP_SETTINGS_KEY].WEBSERVER_CONVERSATIONS  # nosec

    app.router.add_routes(_conversations_rest.routes)
    app.router.add_routes(_conversations_messages_rest.routes)
