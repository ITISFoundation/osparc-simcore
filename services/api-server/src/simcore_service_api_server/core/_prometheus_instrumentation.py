from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest
from prometheus_fastapi_instrumentator import Instrumentator


def instrument_app(app: FastAPI):

    Instrumentator().instrument(app)

    @app.get(
        "/metrics",
        response_class=PlainTextResponse,
        include_in_schema=True,
    )
    def _metrics():
        metrics_data = generate_latest()
        return PlainTextResponse(metrics_data)
