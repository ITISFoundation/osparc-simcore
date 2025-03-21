"""projects management subsystem

A project is a document defining a osparc study
It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..constants import APP_SETTINGS_KEY
from . import (
    _trash_rest,
    _wallets_rest,
)
from ._controller import (
    comments_rest,
    folders_rest,
    groups_rest,
    metadata_rest,
    nodes_pricing_unit_rest,
    nodes_rest,
    ports_rest,
    projects_rest,
    projects_states_rest,
    tags_rest,
    workspaces_rest,
)
from ._controller.projects_slot import setup_project_observer_events
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

    app.router.add_routes(projects_states_rest.routes)
    app.router.add_routes(projects_rest.routes)
    app.router.add_routes(comments_rest.routes)
    app.router.add_routes(groups_rest.routes)
    app.router.add_routes(metadata_rest.routes)
    app.router.add_routes(ports_rest.routes)
    app.router.add_routes(nodes_rest.routes)
    app.router.add_routes(tags_rest.routes)
    app.router.add_routes(_wallets_rest.routes)
    app.router.add_routes(folders_rest.routes)
    app.router.add_routes(nodes_pricing_unit_rest.routes)
    app.router.add_routes(workspaces_rest.routes)
    app.router.add_routes(_trash_rest.routes)

    return True
