import asyncio
import logging
import threading

from celery import Celery  # type: ignore[import-untyped]
from celery.worker.worker import WorkController  # type: ignore[import-untyped]
from servicelib.celery.app_server import BaseAppServer
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings

from .common import create_task_manager
from .utils import get_app_server, set_app_server

_logger = logging.getLogger(__name__)


def on_worker_init(
    app_server: BaseAppServer,
    celery_settings: CelerySettings,
    sender: WorkController,
    **_kwargs,
) -> None:
    startup_complete_event = threading.Event()

    def _init(startup_complete_event: threading.Event) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _setup_task_manager():
            assert sender.app  # nosec
            assert isinstance(sender.app, Celery)  # nosec

            set_app_server(sender.app, app_server)

        app_server.event_loop = loop

        loop.run_until_complete(_setup_task_manager())
        loop.run_until_complete(app_server.lifespan(startup_complete_event))

    thread = threading.Thread(
        group=None,
        target=_init,
        name="app_server_init",
        args=(startup_complete_event,),
        daemon=True,
    )
    thread.start()

    startup_complete_event.wait()


def on_worker_shutdown(sender, **_kwargs) -> None:
    with log_context(_logger, logging.INFO, "Worker shutdown"):
        assert isinstance(sender.app, Celery)
        app_server = get_app_server(sender.app)

        app_server.shutdown_event.set()
