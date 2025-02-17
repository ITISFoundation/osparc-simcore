""" projects management subsystem

    A project is a document defining a osparc study
    It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from . import (
    _comments_rest,
    _crud_handlers,
    _folders_rest,
    _groups_rest,
    _metadata_rest,
    _nodes_rest,
    _ports_handlers,
    _projects_nodes_pricing_unit_handlers,
    _states_handlers,
    _tags_rest,
    _trash_rest,
    _wallets_rest,
    _workspaces_handlers,
)
from ._observer import setup_project_observer_events
from ._projects_access import setup_projects_access
from .db import setup_projects_db

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.projects",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_PROJECTS",
    depends=[f"simcore_service_webserver.{mod}" for mod in ("rest", "db")],
    logger=logger,
)
def setup_projects(app: web.Application) -> bool:
    assert app[APP_SETTINGS_KEY].WEBSERVER_PROJECTS  # nosec

    # security access : Inject permissions to rest API resources
    setup_projects_access(app)

    # database API
    setup_projects_db(app)

    # registers event handlers (e.g. on_user_disconnect)
    setup_project_observer_events(app)

    app.router.add_routes(_states_handlers.routes)
    app.router.add_routes(_crud_handlers.routes)
    app.router.add_routes(_comments_rest.routes)
    app.router.add_routes(_groups_rest.routes)
    app.router.add_routes(_metadata_rest.routes)
    app.router.add_routes(_ports_handlers.routes)
    app.router.add_routes(_nodes_rest.routes)
    app.router.add_routes(_tags_rest.routes)
    app.router.add_routes(_wallets_rest.routes)
    app.router.add_routes(_folders_rest.routes)
    app.router.add_routes(_projects_nodes_pricing_unit_handlers.routes)
    app.router.add_routes(_workspaces_handlers.routes)
    app.router.add_routes(_trash_rest.routes)

    return True
