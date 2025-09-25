"""tags management subsystem"""

import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from . import _rest

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_TAGS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_tags(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_TAGS  # nosec
    app.router.add_routes(_rest.routes)
