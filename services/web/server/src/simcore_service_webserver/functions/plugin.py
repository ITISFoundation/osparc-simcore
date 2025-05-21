import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._controller import _functions_rest, _functions_rpc

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_FUNCTIONS",
    logger=_logger,
)
def setup_functions(app: web.Application):
    app.on_startup.append(_functions_rpc.register_rpc_routes_on_startup)
    app.router.add_routes(_functions_rest.routes)
