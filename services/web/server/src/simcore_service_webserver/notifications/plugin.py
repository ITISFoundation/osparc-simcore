"""
    computation module is the main entry-point for computational backend

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..diagnostics.plugin import setup_diagnostics
from ..rabbitmq import setup_rabbitmq
from ..socketio.plugin import setup_socketio
from ..wallets.plugin import setup_wallets
from . import (
    _rabbitmq_exclusive_queue_consumers,
    _rabbitmq_nonexclusive_queue_consumers,
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

    # depends on WalletCreditsMessage
    setup_wallets(app)

    setup_rabbitmq(app)
    setup_socketio(app)
    # Subscribe to rabbit upon startup for logs, progress and other
    # metrics on the execution reported by sidecars
    app.cleanup_ctx.append(
        _rabbitmq_exclusive_queue_consumers.on_cleanup_ctx_rabbitmq_consumers
    )
    app.cleanup_ctx.append(
        _rabbitmq_nonexclusive_queue_consumers.on_cleanup_ctx_rabbitmq_consumers
    )
