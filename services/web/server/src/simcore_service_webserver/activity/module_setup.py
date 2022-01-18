import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from .._constants import APP_OPENAPI_SPECS_KEY
from . import handlers
from .settings import assert_valid_config

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.activity",
    category=ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_activity(app: web.Application):

    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    assert_valid_config(app)
    # ---------------------------------------------

    # setup routes ------------
    specs = app[APP_OPENAPI_SPECS_KEY]

    def include_path(tup_object):
        _method, path, _operation_id, _tags = tup_object
        return any(tail in path for tail in ["/activity/status"])

    handlers_dict = {"get_status": handlers.get_status}

    routes = map_handlers_with_operations(
        handlers_dict, filter(include_path, iter_path_operations(specs)), strict=True
    )
    app.router.add_routes(routes)
