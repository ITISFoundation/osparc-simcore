from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def instrument_app(app: FastAPI):

    Instrumentator().instrument(app).expose(app)
