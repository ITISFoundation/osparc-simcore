from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def instrument_app(app: FastAPI):

    Instrumentator(
        should_instrument_requests_inprogress=True, inprogress_labels=False
    ).instrument(app).expose(app)
