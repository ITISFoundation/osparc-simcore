""" projects management subsystem

    A project is a document defining a osparc study
    It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    get_handlers_from_namespace,
    iter_path_operations,
    map_handlers_with_operations,
)

from .._constants import APP_OPENAPI_SPECS_KEY, APP_SETTINGS_KEY
from . import (
    _comments_handlers,
    _handlers,
    _handlers_crud,
    _metadata_handlers,
    _nodes_handlers,
    _ports_handlers,
    _tags_handlers,
)
from ._observer import setup_project_observer_events
from ._projects_access import setup_projects_access
from .db import setup_projects_db

logger = logging.getLogger(__name__)


def _create_routes(tag, specs, *handlers_module):
    handlers = {}
    for mod in handlers_module:
        handlers.update(get_handlers_from_namespace(mod))

    return map_handlers_with_operations(
        handlers,
        filter(
            lambda o: tag in o.tags and "snapshot" not in o.path,
            iter_path_operations(specs),
        ),
        strict=False,
    )


@app_module_setup(
    "simcore_service_webserver.projects",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_PROJECTS",
    depends=[f"simcore_service_webserver.{mod}" for mod in ("rest", "db")],
    logger=logger,
)
def setup_projects(app: web.Application) -> bool:
    assert app[APP_SETTINGS_KEY].WEBSERVER_PROJECTS  # nosec

    # API routes
    specs = app[APP_OPENAPI_SPECS_KEY]

    # security access : Inject permissions to rest API resources
    setup_projects_access(app)

    # database API
    setup_projects_db(app)

    # registers event handlers (e.g. on_user_disconnect)
    setup_project_observer_events(app)

    app.router.add_routes(_handlers.routes)
    app.router.add_routes(_handlers_crud.routes)
    app.router.add_routes(_comments_handlers.routes)
    app.router.add_routes(_metadata_handlers.routes)
    app.router.add_routes(_ports_handlers.routes)

    app.router.add_routes(
        _create_routes(
            "project",
            specs,
            _nodes_handlers,
            _tags_handlers,
        )
    )

    # FIXME: this uses some unimplemented handlers, do we really need to keep this in?
    # app.router.add_routes( _create_routes("node", specs, nodes_handlers) )

    return True
