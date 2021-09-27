from fastapi import FastAPI
from fastapi_contrib.tracing.middlewares import OpentracingMiddleware
from fastapi_contrib.tracing.utils import setup_opentracing


async def setup_tracing(app: FastAPI):
    setup_opentracing(app)
    app.add_middleware(OpentracingMiddleware)
