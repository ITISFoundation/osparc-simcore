from fastapi import Depends, FastAPI
from fastapi.requests import Request

from ...modules.pennsieve import PennsieveApiClient


def _get_app(request: Request) -> FastAPI:
    return request.app


def get_pennsieve_api_client(
    app: FastAPI = Depends(_get_app),
) -> PennsieveApiClient:
    return PennsieveApiClient.get_instance(app)
