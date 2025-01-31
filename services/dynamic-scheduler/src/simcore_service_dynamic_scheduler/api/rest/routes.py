from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from servicelib.fastapi.exceptions_utils import (
    handle_errors_as_500,
    http_exception_as_json_response,
)

from ..._meta import API_VTAG
from . import _health, _meta


@asynccontextmanager
async def lifespan_rest_api(app: FastAPI) -> AsyncIterator[None]:
    app.include_router(_health.router)

    api_router = APIRouter(prefix=f"/{API_VTAG}")
    api_router.include_router(_meta.router, tags=["meta"])
    app.include_router(api_router)

    app.add_exception_handler(Exception, handle_errors_as_500)
    app.add_exception_handler(HTTPException, http_exception_as_json_response)

    yield
