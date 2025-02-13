import logging
from multiprocessing import Process
from typing import Callable, cast

from celery import Celery
from celery.apps.worker import Worker
from celery.result import AsyncResult
from fastapi import FastAPI
from settings_library.redis import RedisDatabase
from simcore_service_storage.modules.celery.tasks import archive

from ...core.settings import get_application_settings

_log = logging.getLogger(__name__)


class CeleryTaskQueue:
    def __init__(self, celery_app: Celery):
        self._celery_app = celery_app

    def create_task(self, task_fn: Callable):
        self._celery_app.task()(task_fn)

    def send_task(self, name: str, **kwargs) -> AsyncResult:
        return self._celery_app.send_task(name, **kwargs)

    def cancel_task(self, task_id: str):
        self._celery_app.control.revoke(task_id)


# TODO: move and use new FastAPI lifespan
def setup_celery(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings = get_application_settings(app)
        assert settings.STORAGE_REDIS

        assert settings.STORAGE_REDIS
        redis_dsn = settings.STORAGE_REDIS.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        )

        celery_app = Celery(
            broker=redis_dsn,
            backend=redis_dsn,
        )

        task_queue = CeleryTaskQueue(celery_app)
        task_queue.create_task(archive)

        app.state.task_queue = task_queue

        # FIXME: Experiment: to start worker in a separate process
        def worker_process():
            worker = Worker(app=app.state.celery_app)
            worker.start()

        worker_proc = Process(target=worker_process)
        worker_proc.start()

    async def on_shutdown() -> None:
        _log.warning("Implementing shutdown of celery app")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_celery_task_queue(app: FastAPI) -> CeleryTaskQueue:
    return cast(CeleryTaskQueue, app.state.task_queue)
