from fastapi import APIRouter, FastAPI

from .._meta import API_VTAG
from . import _acknowledgements, _auth, _health, _meta


def setup_rest_api_routes(app: FastAPI):
    app.include_router(_health.router)

    api_router = APIRouter(prefix=f"/{API_VTAG}")
    api_router.include_router(_auth.router, tags=["auth"])
    api_router.include_router(_meta.router, tags=["meta"])
    api_router.include_router(_acknowledgements.router, tags=["acks"])
    app.include_router(api_router)
