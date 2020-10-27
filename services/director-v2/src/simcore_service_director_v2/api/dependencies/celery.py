from fastapi import Request

from ...modules.celery import CeleryClient


class CeleryApp:
    def __init__(self, request: Request):
        self.client = CeleryClient.instance(request.app)
