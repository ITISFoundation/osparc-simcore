from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from . import _invitations, _meta


def setup_api_routes(app: FastAPI):
    """
    Composes resources/sub-resources routers
    """

    router = APIRouter()
    router.include_router(_meta.router, tags=["meta"])
    router.include_router(_invitations.router, tags=["invitations"])

    app.include_router(router, prefix=f"/{API_VTAG}")
