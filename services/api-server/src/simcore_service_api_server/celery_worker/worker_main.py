"""Main application to be deployed in for example uvicorn."""

from functools import partial

from celery_library.common import create_app as create_celery_app
from celery_library.signals import (
    on_worker_init,
)
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.logging_utils import setup_loggers
from servicelib.tracing import TracingData

from ..core.application import create_app
from ..core.settings import ApplicationSettings
from .worker_tasks.tasks import setup_worker_tasks


def get_app():
    _settings = ApplicationSettings.create_from_envs()
    tracing_data: TracingData | None = None
    if _settings.API_SERVER_TRACING:
        tracing_data = TracingData.create(
            tracing_settings=_settings.API_SERVER_TRACING,
            service_name="api-server-celery-worker",
        )

    setup_loggers(
        log_format_local_dev_enabled=_settings.API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=_settings.API_SERVER_LOG_FILTER_MAPPING,
        tracing_settings=_settings.API_SERVER_TRACING,
        tracing_data=tracing_data,
        log_base_level=_settings.log_level,
        noisy_loggers=None,
    )

    assert _settings.API_SERVER_CELERY  # nosec
    app = create_celery_app(_settings.API_SERVER_CELERY)
    setup_worker_tasks(app)

    return app


def worker_init_wrapper(sender, **_kwargs):
    _settings = ApplicationSettings.create_from_envs()
    assert _settings.API_SERVER_CELERY  # nosec
    app_server = FastAPIAppServer(app=create_app(_settings))

    return partial(on_worker_init, app_server=app_server)(sender, **_kwargs)
