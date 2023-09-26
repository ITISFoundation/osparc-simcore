"""
    computation module is the main entry-point for computational backend

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..diagnostics.plugin import setup_diagnostics
from ..rabbitmq import setup_rabbitmq
from ..socketio.plugin import setup_socketio
from ._rabbitmq_consumers import setup_rabbitmq_consumers
from ._rabbitmq_osparc_credits_consumer import (
    setup_rabbitmq_consumers as setup_rabbitmq_osparc_credits_consumers,
)

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
    app.cleanup_ctx.append(setup_rabbitmq_osparc_credits_consumers)
