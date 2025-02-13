import logging

from celery import Celery
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings

_log = logging.getLogger(__name__)


def create_celery_app(settings: ApplicationSettings) -> Celery:
    assert settings.STORAGE_REDIS
    app = Celery(
        broker=settings.STORAGE_REDIS.build_redis_dsn(RedisDatabase.CELERY_TASKS),
        backend=settings.STORAGE_REDIS.build_redis_dsn(RedisDatabase.CELERY_TASKS),
    )
    return app
