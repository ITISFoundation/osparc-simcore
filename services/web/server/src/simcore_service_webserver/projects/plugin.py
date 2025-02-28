"""projects management subsystem

A project is a document defining a osparc study
It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

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
        _comments_rest,
        _folders_rest,
        _groups_rest,
        _metadata_rest,
        _nodes_pricing_unit_rest,
        _nodes_rest,
        _ports_rest,
        _projects_rest,
        _projects_slots,
        _tags_rest,
        _trash_rest,
        _wallets_rest,
        _workspaces_rest,
    )

    assert app[APP_SETTINGS_KEY].WEBSERVER_PROJECTS  # nosec

    # security access : Inject permissions to rest API resources
    _security_service.setup_projects_access(app)

    # database API
    _projects_repository_legacy.setup_projects_db(app)

    # slots: registers event handlers (e.g. on_user_disconnect)
    _projects_slots.setup_project_observer_events(app)

    # rest
    app.router.add_routes(_projects_rest.routes)
    app.router.add_routes(_comments_rest.routes)
    app.router.add_routes(_groups_rest.routes)
    app.router.add_routes(_metadata_rest.routes)
    app.router.add_routes(_ports_rest.routes)
    app.router.add_routes(_nodes_rest.routes)
    app.router.add_routes(_tags_rest.routes)
    app.router.add_routes(_wallets_rest.routes)
    app.router.add_routes(_folders_rest.routes)
    app.router.add_routes(_nodes_pricing_unit_rest.routes)
    app.router.add_routes(_workspaces_rest.routes)
    app.router.add_routes(_trash_rest.routes)

    return True
