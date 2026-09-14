"""
computation module is the main entry-point for computational backend

"""

import datetime
import logging
from collections.abc import AsyncIterator

from aiohttp import web
from servicelib.background_task import periodic_task

from ..application_setup import ModuleCategory, app_setup_func
from ..db.plugin import setup_db
from ..projects._projects_repository_legacy import setup_projects_db
from ..socketio.socketio_service import setup_socketio
from ._db_comp_tasks_listening_task import _OUTBOX_POLL_INTERVAL_S, _listen_and_poll

_logger = logging.getLogger(__name__)


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    async with periodic_task(
        _listen_and_poll,
        interval=datetime.timedelta(seconds=_OUTBOX_POLL_INTERVAL_S),
        task_name="outbox projector",
        app=app,
    ):
        yield


@app_setup_func(
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
