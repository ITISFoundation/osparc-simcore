""" director subsystem

    Provides interactivity with the director service
"""

import logging

from aiohttp import web, ClientSession

from servicelib.application_keys import APP_CONFIG_KEY

from .config import CONFIG_SECTION_NAME, APP_DIRECTOR_SESSION_KEY, APP_DIRECTOR_API_KEY, build_api_url
from . import handlers
from servicelib.rest_routing import get_handlers_from_namespace, map_handlers_with_operations, iter_path_operations
from ..rest_config import APP_OPENAPI_SPECS_KEY

from yarl import URL

logger = logging.getLogger(__name__)

async def director_client_ctx(app: web.Application):
    # TODO: deduce base url from configuration and add to session
    # TODO: test if ready!

    session = ClientSession(loop=app.loop)
    app[APP_DIRECTOR_SESSION_KEY] = session

    # TODO: create instead a class that wraps the session and hold all information known upon setup
    session.base_url = app[APP_DIRECTOR_API_KEY]

    yield

    session.close()
    logger.debug("cleanup session")


def setup(app: web.Application,* , disable_login=False):
    """

    :param app: main application
    :type app: web.Application
    :param disable_login: disabled auth requirements for subsystem's rest (for debugging), defaults to False
    :param disable_login: bool, optional
    """
    logger.debug("Setting up %s ...", __name__)

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    if not cfg["enabled"]:
        logger.warning("'%s' explicitly disabled in config", __name__)
        return

    # director service API endpoint
    app[APP_DIRECTOR_API_KEY] = build_api_url(cfg)

    # Setup routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    def include_path(tup_object):
        _method, path, _operation_id = tup_object
        return any( tail in path  for tail in ['/running_interactive_services', '/services'] )

    handlers_dict = {
        'running_interactive_services_post': handlers.running_interactive_services_post ,
        'running_interactive_services_get': handlers.running_interactive_services_get,
        'running_interactive_services_delete': handlers.running_interactive_services_delete,
        'services_get': handlers.services_get
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

    app.cleanup_ctx.append(director_client_ctx)


# alias
setup_director = setup

__all__ = (
    'setup_director'
)
