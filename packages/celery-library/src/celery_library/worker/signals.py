import asyncio
import threading
from collections.abc import Callable

from celery import Celery  # type: ignore[import-untyped]
from celery.signals import (  # type: ignore[import-untyped]
    worker_init,
    worker_process_init,
    worker_process_shutdown,
    worker_shutdown,
)
from servicelib.celery.app_server import BaseAppServer
from settings_library.celery import CelerySettings

from .app_server import get_app_server, set_app_server


def register_worker_signals(
    app: Celery,
    settings: CelerySettings,
    app_server_factory: Callable[[], BaseAppServer],
) -> None:
    def _worker_init_wrapper(**_kwargs) -> None:
        startup_complete_event = threading.Event()

        def _init(startup_complete_event: threading.Event) -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            app_server = app_server_factory()
            app_server.event_loop = loop

            set_app_server(app, app_server)

            loop.run_until_complete(
                app_server.run_until_shutdown(startup_complete_event)
            )

        thread = threading.Thread(
            group=None,
            target=_init,
            name="app_server_init",
            args=(startup_complete_event,),
            daemon=True,
        )
        thread.start()

        startup_complete_event.wait()

    def _worker_shutdown_wrapper(**_kwargs) -> None:
        get_app_server(app).shutdown_event.set()

    match settings.CELERY_POOL:
        case "prefork":
            worker_process_init.connect(_worker_init_wrapper, weak=False)
            worker_process_shutdown.connect(_worker_shutdown_wrapper, weak=False)
        case _:
            worker_init.connect(_worker_init_wrapper, weak=False)
            worker_shutdown.connect(_worker_shutdown_wrapper, weak=False)
