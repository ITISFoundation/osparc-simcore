from typing import Callable

from fastapi import FastAPI
from fastapi_contrib.tracing.middlewares import OpentracingMiddleware
from fastapi_contrib.tracing.utils import setup_opentracing


def setup_tracing(app: FastAPI) -> Callable:
    async def start_app() -> None:
        setup_opentracing(app)
        app.add_middleware(OpentracingMiddleware)

    return start_app
