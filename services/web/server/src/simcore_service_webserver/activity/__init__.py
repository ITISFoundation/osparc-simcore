import asyncio
import logging

from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import (get_handlers_from_namespace,
                                     iter_path_operations,
                                     map_handlers_with_operations)

from ..rest_config import APP_OPENAPI_SPECS_KEY
from . import handlers
from .config import CONFIG_SECTION_NAME

logger = logging.getLogger(__name__)

def setup(app: web.Application,* , disable_login=False):

    logger.debug("Setting up %s ...", __name__)

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    if not cfg["enabled"]:
        logger.warning("'%s' explicitly disabled in config", __name__)
        return


    # setup routes ------------
    specs = app[APP_OPENAPI_SPECS_KEY]

    def include_path(tup_object):
        _method, path, _operation_id = tup_object
        return any( tail in path  for tail in ['/activity/status'] )

    handlers_dict = {
        'get_status': handlers.get_status        
    }

    # Disables login_required decorator for testing purposes
    if disable_login:
        for name, hnds in handlers_dict.items():
            if hasattr(hnds, '__wrapped__'):
                handlers_dict[name] = hnds.__wrapped__

    routes = map_handlers_with_operations(
        handlers_dict,
        filter(include_path, iter_path_operations(specs)),
        strict=True
    )
    app.router.add_routes(routes)


# alias
setup_activity = setup

__all__ = (
    'setup_activity'
)
