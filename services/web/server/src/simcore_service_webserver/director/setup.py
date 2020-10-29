""" director subsystem

    Provides access to the director backend service
"""

import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from ..rest_config import APP_OPENAPI_SPECS_KEY
from .config import APP_DIRECTOR_API_KEY, CONFIG_SECTION_NAME, DirectorSettings

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.director",
    ModuleCategory.ADDON,
    depends=[],
    logger=logger,
)
def setup_director(app: web.Application, *, disable_login=False, **cfg_settings):
    """Sets up director's subsystem

    :param app: main application
    :type app: web.Application
    :param disable_login: disabled auth requirements for subsystem's rest (for debugging), defaults to False
    :param disable_login: bool, optional
    """
    cfg = DirectorSettings(**cfg_settings)
    app[APP_CONFIG_KEY][CONFIG_SECTION_NAME] = cfg

    # director service API base url, e.g. http://director:8081/v0
    app[APP_DIRECTOR_API_KEY] = cfg.base_url

    # setup routes ------------
    specs = app[APP_OPENAPI_SPECS_KEY]

    def include_path(tup_object):
        _method, path, _operation_id, _tags = tup_object
        return any(tail in path for tail in ["/running_interactive_services"])

    handlers_dict = {}

    # Disables login_required decorator for testing purposes
    if disable_login:
        for name, hnds in handlers_dict.items():
            if hasattr(hnds, "__wrapped__"):
                handlers_dict[name] = hnds.__wrapped__

    routes = map_handlers_with_operations(
        handlers_dict, filter(include_path, iter_path_operations(specs)), strict=True
    )
    app.router.add_routes(routes)


__all__ = "setup_director"
