""" projects management subsystem

    A project is a document defining a osparc study
    It contains metadata about the study (e.g. name, description, owner, etc) and a workbench section that describes the study pipeline
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..constants import APP_SETTINGS_KEY
from ..folders.plugin import setup_folders
from ..projects.plugin import setup_projects
from ..workspaces.plugin import setup_workspaces
from . import _rest

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_TRASH",
    logger=_logger,
)
def setup_trash(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_TRASH  # nosec

    setup_projects(app)
    setup_folders(app)
    setup_workspaces(app)

    app.router.add_routes(_rest.routes)
