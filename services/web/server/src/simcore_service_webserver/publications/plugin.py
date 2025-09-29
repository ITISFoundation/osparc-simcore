"""publications management subsystem"""

import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..email.plugin import setup_email
from ..products.plugin import setup_products
from . import _rest

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    settings_name="WEBSERVER_PUBLICATIONS",
    logger=_logger,
)
def setup_publications(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_PUBLICATIONS  # nosec

    setup_email(app)
    setup_products(app)

    app.router.add_routes(_rest.routes)
