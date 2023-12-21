from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from prometheus_client import generate_latest
from prometheus_fastapi_instrumentator import Instrumentator


def instrument_app(app: FastAPI):

    Instrumentator().instrument(app)

    @app.get(
        "/metrics",
        response_class=PlainTextResponse,
        include_in_schema=True,
    )
    def _metrics(credentials: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())]):
        return PlainTextResponse(generate_latest())
