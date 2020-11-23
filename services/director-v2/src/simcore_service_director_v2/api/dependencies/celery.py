from fastapi import Request

from ...modules.celery import CeleryClient


def get_celery_client(request: Request) -> CeleryClient:
    return CeleryClient.instance(request.app)
