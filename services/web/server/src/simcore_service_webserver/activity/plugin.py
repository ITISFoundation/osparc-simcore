import logging

from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_routing import iter_path_operations, map_handlers_with_operations

from ..rest_config import APP_OPENAPI_SPECS_KEY
from . import handlers
from .config import CONFIG_SECTION_NAME, ActivitySettings

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    category=ModuleCategory.ADDON,
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_activity(app: web.Application, **cfg_settings):

    # submodule settings and store in app
    cfg = ActivitySettings(**cfg_settings)
    app[APP_CONFIG_KEY][CONFIG_SECTION_NAME] = cfg

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
