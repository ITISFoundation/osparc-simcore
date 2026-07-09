from collections.abc import Callable

from celery import Celery  # type: ignore[import-untyped]
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from servicelib.celery.app_server import BaseAppServer
from servicelib.logging_utils import LogLevelInt
from servicelib.tracing import TracingConfig
from settings_library.celery import CelerySettings

from ..app import create_app
from .signals import register_worker_signals


def create_worker_app(
    settings: CelerySettings,
    register_worker_tasks_cb: Callable[[Celery], None],
    app_server_factory_cb: Callable[[], BaseAppServer],
    *,
    log_format_local_dev_enabled: bool,
    logger_filter_mapping: dict[LoggerName, list[MessageSubstring]],
    tracing_config: TracingConfig,
    log_base_level: LogLevelInt,
    noisy_loggers: tuple[str, ...] | None,
) -> Celery:
    app = create_app(settings)
    register_worker_tasks_cb(app)
    register_worker_signals(
        app,
        settings,
        app_server_factory_cb,
        log_format_local_dev_enabled=log_format_local_dev_enabled,
        logger_filter_mapping=logger_filter_mapping,
        tracing_config=tracing_config,
        log_base_level=log_base_level,
        noisy_loggers=noisy_loggers,
    )

    return app
