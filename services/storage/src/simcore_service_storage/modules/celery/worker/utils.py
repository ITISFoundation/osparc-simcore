from asyncio import AbstractEventLoop

from celery import Celery
from fastapi import FastAPI

from ._interface import CeleryWorkerInterface


def get_fastapi_app(celery_app: Celery) -> FastAPI:
    fast_api_app: FastAPI = celery_app.conf.get("fastapi_app")
    return fast_api_app


def get_loop(celery_app: Celery) -> AbstractEventLoop:  # nosec
    loop: AbstractEventLoop = celery_app.conf.get("loop")
    return loop


def get_worker_interface(celery_app: Celery) -> CeleryWorkerInterface:
    worker_interface: CeleryWorkerInterface = celery_app.conf.get("worker_interface")
    return worker_interface
