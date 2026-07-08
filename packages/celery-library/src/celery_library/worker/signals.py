import asyncio
import threading
from collections.abc import Callable

from celery import Celery  # type: ignore[import-untyped]
from celery.signals import (  # type: ignore[import-untyped]
    heartbeat_sent,
    setup_logging,
    worker_init,
    worker_process_init,
    worker_process_shutdown,
    worker_shutdown,
)
from common_library.heartbeat import update_heartbeat
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from servicelib.celery.app_server import BaseAppServer
from servicelib.logging_utils import LogLevelInt, setup_loggers
from servicelib.tracing import TracingConfig
from settings_library.celery import CeleryPoolType, CelerySettings

from .app_server import get_app_server, set_app_server


def _worker_init_wrapper(app: Celery, app_server_factory: Callable[[], BaseAppServer]) -> Callable[..., None]:
    def _worker_init_handler(**_kwargs) -> None:
        startup_complete_event = threading.Event()

        def _init(startup_complete_event: threading.Event) -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            app_server = app_server_factory()
            app_server.event_loop = loop

            set_app_server(app, app_server)

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

    return _worker_init_handler


def _worker_shutdown_wrapper(app: Celery) -> Callable[..., None]:
    def _worker_shutdown_handler(**_kwargs) -> None:
        get_app_server(app).shutdown_event.set()

    return _worker_shutdown_handler


def _setup_logging_wrapper(
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_config: TracingConfig,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> Callable[..., None]:
    def _setup_logging_handler(**_kwargs) -> None:
        setup_loggers(
            log_format_local_dev_enabled=log_format_local_dev_enabled,
            logger_filter_mapping=logger_filter_mapping,
            tracing_config=tracing_config,
            log_base_level=log_base_level,
            noisy_loggers=noisy_loggers,
        )

    return _setup_logging_handler


def register_worker_signals(
    app: Celery,
    settings: CelerySettings,
    app_server_factory: Callable[[], BaseAppServer],
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_config: TracingConfig,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> None:
    setup_logging.connect(
        _setup_logging_wrapper(
            log_format_local_dev_enabled=log_format_local_dev_enabled,
            logger_filter_mapping=logger_filter_mapping,
            tracing_config=tracing_config,
            log_base_level=log_base_level,
            noisy_loggers=noisy_loggers,
        ),
        weak=False,
    )

    match settings.CELERY_POOL:
        case CeleryPoolType.PREFORK:
            worker_process_init.connect(_worker_init_wrapper(app, app_server_factory), weak=False)
            worker_process_shutdown.connect(_worker_shutdown_wrapper(app), weak=False)
        case _:
            worker_init.connect(_worker_init_wrapper(app, app_server_factory), weak=False)
            worker_shutdown.connect(_worker_shutdown_wrapper(app), weak=False)

    heartbeat_sent.connect(lambda **_kwargs: update_heartbeat(), weak=False)
