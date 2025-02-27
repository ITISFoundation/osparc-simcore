import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..constants import APP_SETTINGS_KEY
from ..db.plugin import setup_db
from ..products.plugin import setup_products
from ..rabbitmq import setup_rabbitmq
from ..rest.plugin import setup_rest
from . import _rest, _rpc

_logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.api_keys",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_API_KEYS",
    logger=_logger,
)
def setup_api_keys(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_API_KEYS  # nosec
    setup_db(app)
    setup_products(app)

    # http api
    setup_rest(app)
    app.router.add_routes(_rest.routes)

    # rpc api
    setup_rabbitmq(app)
    if app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(_rpc.register_rpc_routes_on_startup)
