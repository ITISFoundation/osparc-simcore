import logging
from multiprocessing import Process
from typing import cast

from celery import Celery
from celery.apps.worker import Worker
from fastapi import FastAPI
from settings_library.redis import RedisDatabase
from simcore_service_storage.modules.celery.tasks import setup_celery_tasks

from ...core.settings import get_application_settings

_log = logging.getLogger(__name__)


def setup_celery(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings = get_application_settings(app)
        assert settings.STORAGE_REDIS

        redis_dsn = settings.STORAGE_REDIS.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        )

        app.state.celery_app = Celery(
            broker=redis_dsn,
            backend=redis_dsn,
        )

        setup_celery_tasks(app.state.celery_app)

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


def get_celery_app(app: FastAPI) -> Celery:
    return cast(Celery, app.state.celery_app)
