from functools import partial

from celery_library.worker.app import create_worker_app
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.logging_utils import setup_loggers
from servicelib.tracing import TracingConfig

from ...api.celery.tasks import register_worker_tasks
from ...core.application import create_app
from ...core.settings import ApplicationSettings


def get_app():
    settings = ApplicationSettings.create_from_envs()
    tracing_config = TracingConfig.create(
        tracing_settings=settings.NOTIFICATIONS_TRACING,
        service_name="notifications-celery-worker",
    )

    setup_loggers(
        log_format_local_dev_enabled=settings.NOTIFICATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.NOTIFICATIONS_LOG_FILTER_MAPPING,
        tracing_config=tracing_config,
        log_base_level=settings.log_level,
        noisy_loggers=None,
    )

    def _app_server_factory() -> FastAPIAppServer:
        fastapi_app = create_app(settings, tracing_config=tracing_config)
        return FastAPIAppServer(app=fastapi_app)

    assert settings.NOTIFICATIONS_CELERY  # nosec
    return create_worker_app(
        settings.NOTIFICATIONS_CELERY,
        register_worker_tasks_cb=partial(register_worker_tasks, settings),
        app_server_factory_cb=_app_server_factory,
    )


app = get_app()
