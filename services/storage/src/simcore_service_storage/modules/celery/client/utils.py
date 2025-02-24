import logging

from celery import Celery
from fastapi import FastAPI

from ._interface import CeleryClientInterface

_log = logging.getLogger(__name__)


def attach_to_fastapi(fastapi: FastAPI, celery: Celery) -> None:
    fastapi.state.celery = celery


def get_celery_client(fastapi: FastAPI) -> CeleryClientInterface:
    celery: Celery = fastapi.state.celery
    return celery.conf.get("client_interface")
