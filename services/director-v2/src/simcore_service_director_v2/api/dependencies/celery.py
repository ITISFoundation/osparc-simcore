from typing import Callable
from fastapi import Request

from ...modules.celery import CeleryClient


def get_celery_client(request: Request) -> CeleryClient:
    client = CeleryClient.instance(request.app)

    return client
