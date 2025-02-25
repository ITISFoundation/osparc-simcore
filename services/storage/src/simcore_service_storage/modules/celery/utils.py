from celery import Celery
from fastapi import FastAPI
from simcore_service_storage.main import CeleryTaskQueueClient


def get_celery_client(fastapi: FastAPI) -> CeleryTaskQueueClient:
    celery = fastapi.state.celery_app
    assert isinstance(celery, Celery)

    client = celery.conf["client"]
    assert isinstance(client, CeleryTaskQueueClient)
    return client
