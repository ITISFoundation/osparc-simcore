""" projects management subsystem

    A project is a document defining a osparc study
    It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""
import asyncio
import logging
from pprint import pformat

from aiohttp import ClientSession, web
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from servicelib.application_keys import (APP_CONFIG_KEY,
                                         APP_JSONSCHEMA_SPECS_KEY)
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.client_session import get_client_session
from servicelib.jsonschema_specs import create_jsonschema_specs
from servicelib.rest_routing import (get_handlers_from_namespace,
                                     iter_path_operations,
                                     map_handlers_with_operations)

from ..rest_config import APP_OPENAPI_SPECS_KEY
from . import nodes_handlers, projects_handlers
from .config import CONFIG_SECTION_NAME
from .projects_access import setup_projects_access
from .projects_db import setup_projects_db
from .projects_fakes import Fake

RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30

logger = logging.getLogger(__name__)
module_name = __name__.replace(".__init__", "")

def _create_routes(prefix, handlers_module, specs, *, disable_login=False):
    """
    :param disable_login: Disables login_required decorator for testing purposes defaults to False
    :type disable_login: bool, optional
    """
    # TODO: Remove 'disable_login' and use instead a mock.patch on the decorator!
    handlers = get_handlers_from_namespace(handlers_module)
    if disable_login:
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
async def _get_specs(app, location):
    session = get_client_session(app)
    specs = await create_jsonschema_specs(location, session)
    return specs


@app_module_setup(module_name, ModuleCategory.ADDON,
    depends=[f'simcore_service_webserver.{mod}' for mod in ('rest', 'db') ],
    logger=logger)
def setup(app: web.Application, *, enable_fake_data=False) -> bool:
    """

    :param app: main web application
    :type app: web.Application
    :param enable_fake_data: if True it injects template projects under /data, defaults to False (USE ONLY FOR TESTING)
    :param enable_fake_data: bool, optional
    :return: False if setup skips (e.g. explicitly disabled in config), otherwise True
    :rtype: bool
    """
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    # API routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    # security access : Inject permissions to rest API resources
    setup_projects_access(app)

    # database API
    setup_projects_db(app)

    routes = _create_routes("/projects", projects_handlers, specs)
    app.router.add_routes(routes)

    # FIXME: this uses some unimplemented handlers, do we really need to keep this in?
    # routes = _create_routes("/nodes", nodes_handlers, specs)
    # app.router.add_routes(routes)

    # json-schemas for projects datasets
    project_schema_location = cfg['location']
    loop = asyncio.get_event_loop()
    specs = loop.run_until_complete( _get_specs(app, project_schema_location) )

    if APP_JSONSCHEMA_SPECS_KEY in app:
        app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME] = specs
    else:
        app[APP_JSONSCHEMA_SPECS_KEY] = {CONFIG_SECTION_NAME: specs}

    if enable_fake_data:
        Fake.load_template_projects()

    return True


# alias
setup_projects = setup

__all__ = (
    'setup_projects'
)
