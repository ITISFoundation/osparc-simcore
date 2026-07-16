from fastapi import APIRouter, FastAPI
from servicelib.fastapi.application_setup import ensure_single_setup

from . import _datasets, _files, _health, _locations, _paths, _simcore_s3


@ensure_single_setup
def setup_rest_api_routes(app: FastAPI, vtag: str) -> None:
    # healthcheck at / and at /v0/
    app.include_router(_health.router)

    # api under /v*
    v0_router = APIRouter(prefix=f"/{vtag}")
    v0_router.include_router(_health.router)
    v0_router.include_router(_locations.router)
    v0_router.include_router(_datasets.router)
    v0_router.include_router(_files.router)
    v0_router.include_router(_paths.router)
    v0_router.include_router(_simcore_s3.router)

    app.include_router(v0_router)
