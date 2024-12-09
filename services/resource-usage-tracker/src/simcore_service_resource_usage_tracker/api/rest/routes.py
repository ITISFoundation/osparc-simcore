import logging

from fastapi import APIRouter, FastAPI
from servicelib.logging_utils import log_context

from ..._meta import API_VTAG
from . import _health, _meta, _resource_tracker

_logger = logging.getLogger(__name__)


def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """
    with log_context(
        _logger,
        logging.INFO,
        msg="RUT setup_api_routes",
    ):
        app.include_router(_health.router)

        api_router = APIRouter(prefix=f"/{API_VTAG}")
        api_router.include_router(_meta.router, tags=["meta"])
        api_router.include_router(_resource_tracker.router)
        app.include_router(api_router)
