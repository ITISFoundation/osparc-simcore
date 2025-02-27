import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..constants import APP_SETTINGS_KEY
from ..products.plugin import setup_products
from . import _classifiers_rest, _groups_rest

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GROUPS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_groups(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_GROUPS  # nosec

    # plugin dependencies
    setup_products(app)

    app.router.add_routes(_groups_rest.routes)
    app.router.add_routes(_classifiers_rest.routes)
