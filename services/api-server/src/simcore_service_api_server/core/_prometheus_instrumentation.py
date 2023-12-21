from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from prometheus_fastapi_instrumentator import Instrumentator


def instrument_app(app: FastAPI):

    Instrumentator().instrument(app)

    @app.get(
        "/metrics",
        response_class=PlainTextResponse,
        include_in_schema=False,
    )
    def _metrics():
        return PlainTextResponse(generate_latest())
