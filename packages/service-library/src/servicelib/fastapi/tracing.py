from typing import Callable

from fastapi import FastAPI
from fastapi_contrib.conf import settings
from fastapi_contrib.tracing.middlewares import OpentracingMiddleware
from fastapi_contrib.tracing.utils import setup_opentracing

""" set-up the opentracing facilities in fastapi-based services

    following env variables shall be set:
    CONTRIB_JAEGER_HOST: contains the host name where the Jaeger instance is located (defaults to jaeger)
    CONTRIB_JAEGER_PORT: contains the port of the Jaeger instance (defaults to 5755 - compact legacy)
    CONTRIB_SERVICE_NAME: the name of this service (defaults to "fastapi_contrib")
    CONTRIB_REQUEST_ID_HEADER: the request ID header
    CONTRIB_TRACE_ID_HEADER: the trace ID header (defaults to "X-TRACE-ID")
    CONTRIB_JAEGER_SAMPLER_TYPE: defaults to "probabilistic"
    CONTRIB_JAEGER_SAMPLER_RATE: defaults to 1

"""


def setup_tracing(app: FastAPI, service_name: str) -> Callable:
    async def start_app() -> None:
        settings.service_name = service_name
        setup_opentracing(app)
        app.add_middleware(OpentracingMiddleware)

    return start_app
