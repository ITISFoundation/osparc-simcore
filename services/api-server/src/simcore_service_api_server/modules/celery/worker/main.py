"""Main application to be deployed in for example uvicorn."""

from celery.signals import (  # type: ignore[import-untyped] # pylint: disable=no-name-in-module
    worker_init,
    worker_shutdown,
)
from celery_library.common import create_app as create_celery_app
from celery_library.signals import (
    on_worker_init,
    on_worker_shutdown,
)
from celery_library.utils import get_app_server, set_app_server
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.logging_utils import setup_loggers
from servicelib.tracing import TracingConfig

from ....core.application import create_app
from ....core.settings import ApplicationSettings
from .tasks import setup_worker_tasks

_settings = ApplicationSettings.create_from_envs()
_tracing_settings = _settings.API_SERVER_TRACING
_tracing_config = TracingConfig.create(
    tracing_settings=_tracing_settings,
    service_name="api-server-celery-worker",
)


def get_app():
    setup_loggers(
        log_format_local_dev_enabled=_settings.API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=_settings.API_SERVER_LOG_FILTER_MAPPING,
        tracing_config=_tracing_config,
        log_base_level=_settings.log_level,
        noisy_loggers=None,
    )

    assert _settings.API_SERVER_CELERY  # nosec
    app = create_celery_app(_settings.API_SERVER_CELERY)
    setup_worker_tasks(app)

    return app


the_app = get_app()


@worker_init.connect
def _worker_init_wrapper(**kwargs):
    _settings = ApplicationSettings.create_from_envs()
    assert _settings.API_SERVER_CELERY  # nosec
    app_server = FastAPIAppServer(app=create_app(_settings))
    set_app_server(the_app, app_server)
    return on_worker_init(app_server, **kwargs)


@worker_shutdown.connect
def _worker_shutdown_wrapper(**kwargs):
    app_server = get_app_server(the_app)
    return on_worker_shutdown(app_server, **kwargs)
