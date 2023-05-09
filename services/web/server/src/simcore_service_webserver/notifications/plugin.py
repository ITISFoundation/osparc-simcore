"""
    computation module is the main entry-point for computational backend

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from simcore_service_webserver.diagnostics.plugin import setup_diagnostics

from ..db import setup_db
from ..diagnostics.plugin import setup_diagnostics
from ..rabbitmq import setup_rabbitmq
from ..socketio.plugin import setup_socketio
from ._db_comp_tasks_listening_task import create_comp_tasks_listening_task
from ._rabbitmq_consumers import setup_rabbitmq_consumers

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_NOTIFICATIONS",
    logger=_logger,
)
def setup_notifications(app: web.Application):
    # depends on diagnostics for setting the instrumentation
    setup_diagnostics(app)

    setup_rabbitmq(app)
    setup_socketio(app)
    # Subscribe to rabbit upon startup for logs, progress and other
    # metrics on the execution reported by sidecars
    app.cleanup_ctx.append(setup_rabbitmq_consumers)

    # Creates a task to listen to comp_task pg-db's table events
    setup_db(app)
    app.cleanup_ctx.append(create_comp_tasks_listening_task)
