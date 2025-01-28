from fastapi import APIRouter, FastAPI

from . import _datasets, _files, _health, _locations, _simcore_s3

v0_router = APIRouter()

# health
health_router = _health.router
v0_router.include_router(_health.router)

# locations
v0_router.include_router(_locations.router)

# datasets
v0_router.include_router(_datasets.router)

# files
v0_router.include_router(_files.router)

# simcore-s3
v0_router.include_router(_simcore_s3.router)


def setup_rest_api_routes(app: FastAPI, vtag: str):
    # healthcheck at / and at /v0/
    app.include_router(health_router)
    # api under /v*
    app.include_router(v0_router, prefix=f"/{vtag}")
