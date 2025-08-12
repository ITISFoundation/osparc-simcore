"""projects management subsystem

A project is a document defining a osparc study
It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..constants import APP_SETTINGS_KEY
from ..rabbitmq import setup_rabbitmq
from ._controller import (
    access_rights_rest,
    comments_rest,
    conversations_rest,
    folders_rest,
    metadata_rest,
    nodes_pricing_unit_rest,
    nodes_rest,
    ports_rest,
    projects_rest,
    projects_rpc,
    projects_slot,
    projects_states_rest,
    tags_rest,
    trash_rest,
    wallets_rest,
    workspaces_rest,
)
from ._controller.nodes_rest import register_stop_dynamic_service_task
from ._crud_api_create import register_create_project_task
from ._projects_repository_legacy import setup_projects_db
from ._security_service import setup_projects_access

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

    # setup SLOT-controllers
    projects_slot.setup_project_observer_events(app)

    # setup RPC-controllers
    setup_rabbitmq(app)
    if app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(projects_rpc.register_rpc_routes_on_startup)

    # setup REST-controllers
    app.router.add_routes(projects_states_rest.routes)
    app.router.add_routes(projects_rest.routes)
    app.router.add_routes(comments_rest.routes)
    app.router.add_routes(conversations_rest.routes)
    app.router.add_routes(access_rights_rest.routes)
    app.router.add_routes(metadata_rest.routes)
    app.router.add_routes(ports_rest.routes)
    app.router.add_routes(nodes_rest.routes)
    app.router.add_routes(tags_rest.routes)
    app.router.add_routes(wallets_rest.routes)
    app.router.add_routes(folders_rest.routes)
    app.router.add_routes(nodes_pricing_unit_rest.routes)
    app.router.add_routes(workspaces_rest.routes)
    app.router.add_routes(trash_rest.routes)

    register_create_project_task(app)
    register_stop_dynamic_service_task(app)

    return True
