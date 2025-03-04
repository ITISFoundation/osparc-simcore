import logging

from celery import Celery
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

_logger = logging.getLogger(__name__)


def create_app(celery_settings: CelerySettings) -> Celery:
    assert celery_settings

    app = Celery(
        broker=celery_settings.CELERY_RABBIT_BROKER.dsn,
        backend=celery_settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        ),
    )
    app.conf.result_expires = celery_settings.CELERY_RESULT_EXPIRES
    app.conf.result_extended = True  # original args are included in the results
    app.conf.task_track_started = True
    return app
