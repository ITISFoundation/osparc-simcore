import asyncio
import threading
from collections.abc import Callable

from celery import Celery  # type: ignore[import-untyped]
from celery.signals import (  # type: ignore[import-untyped]
    heartbeat_sent,
    worker_init,
    worker_process_init,
    worker_process_shutdown,
    worker_shutdown,
)
from servicelib.celery.app_server import BaseAppServer
from settings_library.celery import CeleryPoolType, CelerySettings

from .app_server import get_app_server, set_app_server
from .heartbeat import update_heartbeat


def _worker_init_wrapper(
    app: Celery, app_server_factory: Callable[[], BaseAppServer]
) -> Callable[..., None]:
    def _worker_init_handler(**_kwargs) -> None:
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

    return _worker_init_handler


def _worker_shutdown_wrapper(app: Celery) -> Callable[..., None]:
    def _worker_shutdown_handler(**_kwargs) -> None:
        get_app_server(app).shutdown_event.set()

    return _worker_shutdown_handler


def register_worker_signals(
    app: Celery,
    settings: CelerySettings,
    app_server_factory: Callable[[], BaseAppServer],
) -> None:
    match settings.CELERY_POOL:
        case CeleryPoolType.PREFORK:
            worker_process_init.connect(
                _worker_init_wrapper(app, app_server_factory), weak=False
            )
            worker_process_shutdown.connect(_worker_shutdown_wrapper(app), weak=False)
        case _:
            worker_init.connect(
                _worker_init_wrapper(app, app_server_factory), weak=False
            )
            worker_shutdown.connect(_worker_shutdown_wrapper(app), weak=False)

    heartbeat_sent.connect(lambda **_kwargs: update_heartbeat(), weak=False)
