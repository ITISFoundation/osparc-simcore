from fastapi import FastAPI
from fastapi_contrib.conf import settings
from fastapi_contrib.tracing.middlewares import OpentracingMiddleware
from fastapi_contrib.tracing.utils import setup_opentracing
from settings_library.tracing import TracingSettings


def setup_tracing(app: FastAPI, tracing_settings: TracingSettings):
    async def start_app() -> None:
        settings.service_name = tracing_settings.TRACING_CLIENT_NAME
        settings.jaeger_host = tracing_settings.TRACING_THRIFT_COMPACT_ENDPOINT.host
        settings.jaeger_port = tracing_settings.TRACING_THRIFT_COMPACT_ENDPOINT.port
        setup_opentracing(app)
        app.add_middleware(OpentracingMiddleware)

    app.add_event_handler("startup", start_app)
