import logging

from celery import Celery
from fastapi import FastAPI
from settings_library.redis import RedisDatabase

from ....core.settings import ApplicationSettings
from ._interface import CeleryClientInterface

_log = logging.getLogger(__name__)


def create_celery_app(settings: ApplicationSettings) -> Celery:
    assert settings.STORAGE_RABBITMQ
    assert settings.STORAGE_REDIS

    celery_app = Celery(
        broker=settings.STORAGE_RABBITMQ.dsn,
        backend=settings.STORAGE_REDIS.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        ),
    )
    celery_app.conf["client_interface"] = CeleryClientInterface(celery_app)

    return celery_app


def attach_to_fastapi(fastapi: FastAPI, celery: Celery) -> None:
    fastapi.state.celery = celery


def get_celery_client(fastapi: FastAPI) -> CeleryClientInterface:
    celery: Celery = fastapi.state.celery
    return celery.conf.get("client_interface")
