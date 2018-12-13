""" projects management subsystem


"""
import logging
from pprint import pformat

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_routing import (get_handlers_from_namespace,
                                     iter_path_operations,
                                     map_handlers_with_operations)

from . import nodes_handlers, projects_handlers
from ..rest_config import APP_OPENAPI_SPECS_KEY
from .projects_fakes import Fake

CONFIG_SECTION_NAME = "projects"

logger = logging.getLogger(__name__)

def _create_routes(prefix, handlers_module, specs, disable_login):
    handlers = get_handlers_from_namespace(handlers_module)
    if disable_login:
        # Disables login_required decorator for testing purposes
        handlers = { name: hnds.__wrapped__ for name, hnds in handlers.items() }

    routes = map_handlers_with_operations(
            handlers,
            filter(lambda o: prefix in o[1],  iter_path_operations(specs)),
            strict=True
    )

    if disable_login:
        logger.debug("%s-%s:\n%s", CONFIG_SECTION_NAME, prefix, pformat(routes))

    return routes


def setup(app: web.Application, *, enable_fake_data=False, disable_login=False):
    """
    :param app: main web application
    :type app: web.Application
    :param enable_fake_data: will inject some fake projects, defaults to False
    :param enable_fake_data: bool, optional
    :param disable_login: will disable user login for testing, defaults to False
    :param disable_login: bool, optional
    """
    logger.debug("Setting up %s %s...", __name__,
            "[debug]" if enable_fake_data or disable_login
                      else ""
    )

    assert CONFIG_SECTION_NAME not in app[APP_CONFIG_KEY], "Not section for the moment"

    # routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    routes = _create_routes("/projects", projects_handlers, specs, disable_login)
    app.router.add_routes(routes)

    routes = _create_routes("/nodes", nodes_handlers, specs, disable_login)
    app.router.add_routes(routes)

    if enable_fake_data:
        # injects fake projects to User with id=1
        Fake.load_user_projects(user_id=1)
        Fake.load_template_projects()

# alias
setup_projects = setup

__all__ = (
    'setup_projects'
)
