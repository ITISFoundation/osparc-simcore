import asyncio
import logging
import threading

from servicelib.celery.app_server import BaseAppServer
from servicelib.logging_utils import log_context

_logger = logging.getLogger(__name__)


def on_worker_init(app_server: BaseAppServer, **_kwargs) -> None:
    startup_complete_event = threading.Event()

    def _init(startup_complete_event: threading.Event) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        app_server.event_loop = loop

        loop.run_until_complete(app_server.run_until_shutdown(startup_complete_event))

    thread = threading.Thread(
        group=None,
        target=_init,
        name="app_server_init",
        args=(startup_complete_event,),
        daemon=True,
    )
    thread.start()

    startup_complete_event.wait()


def on_worker_shutdown(app_server: BaseAppServer, **_kwargs) -> None:
    with log_context(_logger, logging.INFO, "Worker shutdown"):
        app_server.shutdown_event.set()
