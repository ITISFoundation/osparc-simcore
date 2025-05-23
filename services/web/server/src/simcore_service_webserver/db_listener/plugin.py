"""
computation module is the main entry-point for computational backend

"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..db.plugin import setup_db
from ..projects._projects_repository_legacy import setup_projects_db
from ..socketio.plugin import setup_socketio
from ._db_comp_tasks_listening_task import create_comp_tasks_listening_task

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_DB_LISTENER",
    logger=_logger,
)
def setup_db_listener(app: web.Application):
    setup_socketio(app)
    setup_projects_db(app)
    # Creates a task to listen to comp_task pg-db's table events
    setup_db(app)
    app.cleanup_ctx.append(create_comp_tasks_listening_task)
