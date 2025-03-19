from typing import Annotated, cast

from fastapi import Depends, FastAPI
from fastapi.requests import Request

from ...modules.pennsieve import PennsieveApiClient


def _get_app(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_pennsieve_api_client(
    app: Annotated[FastAPI, Depends(_get_app)],
) -> PennsieveApiClient:
    client = PennsieveApiClient.get_instance(app)
    assert client  # nosec
    return cast(PennsieveApiClient, client)
