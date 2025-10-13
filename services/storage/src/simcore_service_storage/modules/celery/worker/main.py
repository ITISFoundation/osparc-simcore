from celery.signals import (  # type: ignore[import-untyped]
    worker_init,
    worker_process_init,
    worker_process_shutdown,
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

from ....api._worker_tasks.tasks import setup_worker_tasks
from ....core.application import create_app
from ....core.settings import ApplicationSettings

_settings = ApplicationSettings.create_from_envs()
_tracing_config = TracingConfig.create(
    tracing_settings=_settings.STORAGE_TRACING,
    service_name="storage-celery-worker",
)

setup_loggers(
    log_format_local_dev_enabled=_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_settings.STORAGE_LOG_FILTER_MAPPING,
    tracing_config=_tracing_config,
    log_base_level=_settings.log_level,
    noisy_loggers=None,
)

assert _settings.STORAGE_CELERY  # nosec
app = create_celery_app(_settings.STORAGE_CELERY)


@worker_init.connect
@worker_process_init.connect
def worker_init_wrapper(**kwargs):
    fastapi_app = create_app(_settings, tracing_config=_tracing_config)
    app_server = FastAPIAppServer(app=fastapi_app)
    set_app_server(app, app_server)
    return on_worker_init(app_server, **kwargs)


@worker_shutdown.connect
@worker_process_shutdown.connect
def worker_shutdown_wrapper(**kwargs):
    app_server = get_app_server(app)
    return on_worker_shutdown(app_server, **kwargs)


setup_worker_tasks(app)
