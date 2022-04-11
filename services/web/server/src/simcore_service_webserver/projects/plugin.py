""" projects management subsystem

    A project is a document defining a osparc study
    It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""
import logging
from pprint import pformat

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    get_handlers_from_namespace,
    iter_path_operations,
    map_handlers_with_operations,
)

from .._constants import APP_OPENAPI_SPECS_KEY, APP_SETTINGS_KEY
from . import (
    projects_handlers,
    projects_handlers_crud,
    projects_nodes_handlers,
    projects_tags_handlers,
)
from .project_models import setup_projects_model_schema
from .projects_access import setup_projects_access
from .projects_db import setup_projects_db

logger = logging.getLogger(__name__)


def _create_routes(tag, specs, *handlers_module, disable_login: bool = False):
    """
    :param disable_login: Disables login_required decorator for testing purposes defaults to False
    :type disable_login: bool, optional
    """
    # TODO: Remove 'disable_login' and use instead a mock.patch on the decorator!

    handlers = {}
    for mod in handlers_module:
        handlers.update(get_handlers_from_namespace(mod))

    if disable_login:
        handlers = {name: hnds.__wrapped__ for name, hnds in handlers.items()}

    routes = map_handlers_with_operations(
        handlers,
        filter(
            lambda o: tag in o[3] and "snapshot" not in o[2],
            iter_path_operations(specs),
        ),
        strict=True,
    )

    if disable_login:
        logger.debug("%s:\n%s", "projects", pformat(routes))

    return routes


@app_module_setup(
    "simcore_service_webserver.projects",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_PROJECTS",
    depends=[f"simcore_service_webserver.{mod}" for mod in ("rest", "db")],
    logger=logger,
)
def setup_projects(app: web.Application) -> bool:
    assert app[APP_SETTINGS_KEY].WEBSERVER_PROJECTS is True  # nosec

    # API routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    # security access : Inject permissions to rest API resources
    setup_projects_access(app)

    # database API
    setup_projects_db(app)

    app.router.add_routes(
        _create_routes(
            "project",
            specs,
            projects_handlers_crud,
            projects_handlers,
            projects_nodes_handlers,
            projects_tags_handlers,
        )
    )

    # FIXME: this uses some unimplemented handlers, do we really need to keep this in?
    # app.router.add_routes( _create_routes("node", specs, nodes_handlers) )

    # json-schemas for projects datasets
    setup_projects_model_schema(app)
    return True
