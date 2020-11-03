""" projects management subsystem

    A project is a document defining a osparc study
    It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""
import json
import logging
from pprint import pformat

from aiohttp import web

from servicelib.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_routing import (
    get_handlers_from_namespace,
    iter_path_operations,
    map_handlers_with_operations,
)
from . import projects_handlers
from ..resources import resources
from ..rest_config import APP_OPENAPI_SPECS_KEY
from .config import CONFIG_SECTION_NAME, assert_valid_config
from .projects_access import setup_projects_access
from .projects_db import setup_projects_db
from .projects_fakes import Fake

logger = logging.getLogger(__name__)

__all__ = "setup_projects"


def _create_routes(tag, handlers_module, specs, *, disable_login=False):
    """
    :param disable_login: Disables login_required decorator for testing purposes defaults to False
    :type disable_login: bool, optional
    """
    # TODO: Remove 'disable_login' and use instead a mock.patch on the decorator!
    handlers = get_handlers_from_namespace(handlers_module)
    if disable_login:
        handlers = {name: hnds.__wrapped__ for name, hnds in handlers.items()}

    routes = map_handlers_with_operations(
        handlers,
        filter(lambda o: tag in o[3], iter_path_operations(specs)),
        strict=True,
    )

    if disable_login:
        logger.debug("%s:\n%s", CONFIG_SECTION_NAME, pformat(routes))

    return routes


@app_module_setup(
    "simcore_service_webserver.projects",
    ModuleCategory.ADDON,
    depends=[f"simcore_service_webserver.{mod}" for mod in ("rest", "db")],
    logger=logger,
)
def setup_projects(app: web.Application, *, enable_fake_data=False) -> bool:
    """

    :param app: main web application
    :type app: web.Application
    :param enable_fake_data: if True it injects template projects under /data, defaults to False (USE ONLY FOR TESTING)
    :param enable_fake_data: bool, optional
    :return: False if setup skips (e.g. explicitly disabled in config), otherwise True
    :rtype: bool
    """
    # ----------------------------------------------
    # TODO: temporary, just to check compatibility between
    # trafaret and pydantic schemas
    assert_valid_config(app)
    # ---------------------------------------------

    # API routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    # security access : Inject permissions to rest API resources
    setup_projects_access(app)

    # database API
    setup_projects_db(app)

    routes = _create_routes("project", projects_handlers, specs)
    app.router.add_routes(routes)

    # FIXME: this uses some unimplemented handlers, do we really need to keep this in?
    # routes = _create_routes("node", nodes_handlers, specs)
    # app.router.add_routes(routes)

    # json-schemas for projects datasets
    # FIXME: schemas are hard-coded to api/V0!!!
    with resources.stream("api/v0/schemas/project-v0.0.1.json") as fh:
        project_schema = json.load(fh)

    if APP_JSONSCHEMA_SPECS_KEY in app:
        app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME] = project_schema
    else:
        app[APP_JSONSCHEMA_SPECS_KEY] = {CONFIG_SECTION_NAME: project_schema}

    if enable_fake_data:
        Fake.load_template_projects()

    return True
