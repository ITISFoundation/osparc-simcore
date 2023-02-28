"""
    computation module is the main entry-point for computational backend

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .computation_comp_tasks_listening_task import create_comp_tasks_listening_task
from .computation_subscribe import setup_rabbitmq_consumer
from .rabbitmq import setup_rabbitmq

log = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_COMPUTATION",
    logger=log,
    depends=[
        "simcore_service_webserver.diagnostics",
    ],  # depends on diagnostics for setting the instrumentation
)
def setup_computation(app: web.Application):
    setup_rabbitmq(app)
    # Subscribe to rabbit upon startup for logs, progress and other
    # metrics on the execution reported by sidecars
    app.cleanup_ctx.append(setup_rabbitmq_consumer)

    # Creates a task to listen to comp_task pg-db's table events
    app.cleanup_ctx.append(create_comp_tasks_listening_task)
