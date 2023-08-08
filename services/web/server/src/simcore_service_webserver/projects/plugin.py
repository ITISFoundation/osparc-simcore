""" projects management subsystem

    A project is a document defining a osparc study
    It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._constants import APP_SETTINGS_KEY
from . import (
    _comments_handlers,
    _crud_handlers,
    _metadata_handlers,
    _nodes_handlers,
    _ports_handlers,
    _states_handlers,
    _tags_handlers,
    _wallets_handlers,
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
    app.router.add_routes(_comments_handlers.routes)
    app.router.add_routes(_metadata_handlers.routes)
    app.router.add_routes(_ports_handlers.routes)
    app.router.add_routes(_nodes_handlers.routes)
    app.router.add_routes(_tags_handlers.routes)
    app.router.add_routes(_wallets_handlers.routes)

    return True
