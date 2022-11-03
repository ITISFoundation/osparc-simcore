"""
    api app module
"""
from botocore.exceptions import ClientError
from fastapi import APIRouter, FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError

from ..meta import api_vtag
from .errors.http_error import http_error_handler
from .errors.pennsieve_error import botocore_exceptions_handler
from .errors.validation_error import http422_error_handler
from .middleware_timing import add_process_time_header
from .routes import datasets, files, health, user


def setup_api(app: FastAPI):
    router = APIRouter()

    app.include_router(router, prefix=f"/{api_vtag}")
    app.include_router(health.router, tags=["healthcheck"], prefix=f"/{api_vtag}")
    app.include_router(user.router, tags=["user"], prefix=f"/{api_vtag}")
    app.include_router(datasets.router, tags=["datasets"], prefix=f"/{api_vtag}")
    app.include_router(files.router, tags=["files"], prefix=f"/{api_vtag}")

    # exception handlers
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)
    app.add_exception_handler(ClientError, botocore_exceptions_handler)

    # middlewares
    app.middleware("http")(add_process_time_header)
