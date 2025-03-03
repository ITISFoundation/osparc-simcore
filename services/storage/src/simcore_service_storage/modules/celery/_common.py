import logging

from celery import Celery
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> Celery:
    celery_settings = settings.STORAGE_CELERY
    assert celery_settings

    app = Celery(
        broker=celery_settings.CELERY_BROKER.dsn,
        backend=celery_settings.CELERY_RESULT_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        ),
    )
    app.conf.result_expires = celery_settings.CELERY_RESULT_EXPIRES
    app.conf.result_extended = True  # original args are included in the results
    return app
