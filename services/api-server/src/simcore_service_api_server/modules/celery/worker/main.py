from celery_library.worker.app import create_worker_app
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.logging_utils import setup_loggers
from servicelib.tracing import TracingConfig

from ....core.application import create_app
from ....core.settings import ApplicationSettings
from .tasks import register_worker_tasks

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

    def _app_server_factory() -> FastAPIAppServer:
        fastapi_app = create_app(_settings, tracing_config=_tracing_config)
        return FastAPIAppServer(app=fastapi_app)

    assert _settings.API_SERVER_CELERY  # nosec
    return create_worker_app(
        _settings.API_SERVER_CELERY,
        register_worker_tasks,
        _app_server_factory,
    )


app = get_app()
