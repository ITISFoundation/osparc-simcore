import logging
from functools import partial

from celery.signals import worker_init, worker_shutdown  # type: ignore[import-untyped]
from celery_library.common import create_app as create_celery_app
from celery_library.signals import (
    on_worker_init,
    on_worker_shutdown,
)
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.logging_utils import config_all_loggers

from ...core.application import create_app
from ...core.settings import ApplicationSettings
from .tasks import setup_worker_tasks

_settings = ApplicationSettings.create_from_envs()

logging.basicConfig(level=_settings.log_level)  # NOSONAR
logging.root.setLevel(_settings.log_level)
config_all_loggers(
    log_format_local_dev_enabled=_settings.NOTIFICATIONS_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_settings.NOTIFICATIONS_LOG_FILTER_MAPPING,
    tracing_settings=_settings.NOTIFICATIONS_TRACING,
)


assert _settings.NOTIFICATIONS_CELERY  # nosec
the_celery_app = create_celery_app(_settings.NOTIFICATIONS_CELERY)

app_server = FastAPIAppServer(app=create_app())


def worker_init_wrapper(sender, **_kwargs):
    assert _settings.NOTIFICATIONS_CELERY  # nosec
    return partial(on_worker_init, app_server, _settings.NOTIFICATIONS_CELERY)(
        sender, **_kwargs
    )


worker_init.connect(worker_init_wrapper)
worker_shutdown.connect(on_worker_shutdown)

setup_worker_tasks(the_celery_app)
