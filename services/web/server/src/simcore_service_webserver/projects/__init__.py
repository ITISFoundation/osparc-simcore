""" projects management subsystem

TODO: now they are called 'studies'
"""
import asyncio
import logging
from pprint import pformat

from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from aiohttp import web
from servicelib.application_keys import (APP_CONFIG_KEY,
                                         APP_JSONSCHEMA_SPECS_KEY)
from servicelib.jsonschema_specs import create_jsonschema_specs
from servicelib.rest_routing import (get_handlers_from_namespace,
                                     iter_path_operations,
                                     map_handlers_with_operations)

from ..rest_config import APP_OPENAPI_SPECS_KEY
from . import nodes_handlers, projects_handlers
from .config import CONFIG_SECTION_NAME
from .projects_fakes import Fake

RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

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

@retry( wait=wait_fixed(RETRY_WAIT_SECS),
        stop=stop_after_attempt(RETRY_COUNT),
        before_sleep=before_sleep_log(logger, logging.INFO) )
async def _get_specs(location):
    specs = await create_jsonschema_specs(location)
    return specs



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

    assert CONFIG_SECTION_NAME in app[APP_CONFIG_KEY], "{} is missing from configuration".format(CONFIG_SECTION_NAME)
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    if "enabled" in cfg and not cfg["enabled"]:
        logger.warning("'%s' explicitly disabled in config", __name__)
        return

    # API routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    routes = _create_routes("/projects", projects_handlers, specs, disable_login)
    app.router.add_routes(routes)

    routes = _create_routes("/nodes", nodes_handlers, specs, disable_login)
    app.router.add_routes(routes)

    # get project jsonschema definition
    project_schema_location = cfg['location']
    loop = asyncio.get_event_loop()
    specs = loop.run_until_complete( _get_specs(project_schema_location) )
    if APP_JSONSCHEMA_SPECS_KEY in app:
        app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME] = specs
    else:
        app[APP_JSONSCHEMA_SPECS_KEY] = {CONFIG_SECTION_NAME: specs}

    if enable_fake_data:
        Fake.load_template_projects()



# alias
setup_projects = setup

__all__ = (
    'setup_projects'
)
