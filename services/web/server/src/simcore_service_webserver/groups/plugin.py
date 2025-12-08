import logging

from aiohttp import web
from simcore_service_webserver.scicrunch.plugin import setup_scicrunch

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..products.plugin import setup_products
from . import _classifiers_rest, _groups_rest

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GROUPS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_groups(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_GROUPS  # nosec

    # plugin dependencies
    setup_products(app)
    setup_scicrunch(app)

    app.router.add_routes(_groups_rest.routes)
    app.router.add_routes(_classifiers_rest.routes)
