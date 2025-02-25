import logging

from celery import Celery
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def create_app(settings: ApplicationSettings) -> Celery:
    assert settings.STORAGE_CELERY

    app = Celery(
        broker=settings.STORAGE_CELERY.CELERY_BROKER.dsn,
        backend=settings.STORAGE_CELERY.CELERY_RESULTS_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        ),
    )
    return app
