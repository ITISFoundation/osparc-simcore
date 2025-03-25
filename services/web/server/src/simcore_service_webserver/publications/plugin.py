"""publications management subsystem"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..email.plugin import setup_email
from ..products.plugin import setup_products
from . import _rest

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    settings_name="WEBSERVER_PUBLICATIONS",
    logger=_logger,
)
def setup_publications(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_PUBLICATIONS  # nosec

    setup_email(app)
    setup_products(app)

    app.router.add_routes(_rest.routes)
