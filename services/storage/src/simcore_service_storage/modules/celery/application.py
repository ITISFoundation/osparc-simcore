import logging
from typing import cast

from celery import Celery
from celery.result import AsyncResult
from fastapi import FastAPI
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings

_log = logging.getLogger(__name__)


class CeleryTaskQueue:
    def __init__(self, celery_app: Celery):
        self._celery_app = celery_app

    def send_task(self, name: str, *args, **kwargs) -> AsyncResult:
        return self._celery_app.send_task(name, args=args, kwargs=kwargs)

    def cancel_task(self, task_id: str):
        self._celery_app.control.revoke(task_id)


# TODO: move and use new FastAPI lifespan
def create_celery_app(settings: ApplicationSettings) -> Celery:
    assert settings.STORAGE_REDIS

    redis_dsn = settings.STORAGE_REDIS.build_redis_dsn(
        RedisDatabase.CELERY_TASKS,
    )

    celery_app = Celery(
        broker=redis_dsn,
        backend=redis_dsn,
    )

    return celery_app


def get_celery_task_queue(app: FastAPI) -> CeleryTaskQueue:
    return cast(CeleryTaskQueue, app.state.task_queue)
