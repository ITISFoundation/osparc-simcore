""" director subsystem

    Provides access to the director backend service
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from .._constants import APP_OPENAPI_SPECS_KEY
from .settings import get_settings

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.director",
    ModuleCategory.ADDON,
    depends=[],
    logger=logger,
)
def setup_director(
    app: web.Application, *, disable_login: bool = False, disable_routes: bool = False
):
    """Sets up director's app module

    disable_* options are for testing purpuses
    """
    assert get_settings(app)  # nosec

    # setup routes ------------
    if not disable_routes:
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
            handlers_dict,
            filter(include_path, iter_path_operations(specs)),
            strict=True,
        )
        app.router.add_routes(routes)
