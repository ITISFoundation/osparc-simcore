"""projects management subsystem

A project is a document defining a osparc study
It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._controller import (
    comments_rest,
    folders_rest,
    groups_rest,
    metadata_rest,
    nodes_pricing_unit_rest,
    nodes_rest,
    ports_rest,
    projects_rest,
    projects_slots,
    tags_rest,
    trash_rest,
    wallets_rest,
)

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.projects",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_PROJECTS",
    depends=[f"simcore_service_webserver.{mod}" for mod in ("rest", "db")],
    logger=logger,
)
def setup_projects(app: web.Application) -> bool:
    from ..constants import APP_SETTINGS_KEY
    from . import _projects_repository_legacy, _security_service
    from ._controller import (
        workspaces_rest,
    )

    assert app[APP_SETTINGS_KEY].WEBSERVER_PROJECTS  # nosec

    # security access : Inject permissions to rest API resources
    _security_service.setup_projects_access(app)

    # database API
    _projects_repository_legacy.setup_projects_db(app)

    # slots: registers event handlers (e.g. on_user_disconnect)
    projects_slots.setup_project_observer_events(app)

    # rest
    app.router.add_routes(projects_rest.routes)
    app.router.add_routes(comments_rest.routes)
    app.router.add_routes(groups_rest.routes)
    app.router.add_routes(metadata_rest.routes)
    app.router.add_routes(ports_rest.routes)
    app.router.add_routes(nodes_rest.routes)
    app.router.add_routes(tags_rest.routes)
    app.router.add_routes(wallets_rest.routes)
    app.router.add_routes(folders_rest.routes)
    app.router.add_routes(nodes_pricing_unit_rest.routes)
    app.router.add_routes(workspaces_rest.routes)
    app.router.add_routes(trash_rest.routes)

    return True
