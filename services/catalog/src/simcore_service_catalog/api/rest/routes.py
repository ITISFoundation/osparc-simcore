from enum import Enum

from fastapi import APIRouter, FastAPI

from . import (
    _health,
    _meta,
    _services,
    _services_access_rights,
    _services_extras,
    _services_labels,
    _services_ports,
    _services_resources,
    _services_specifications,
)

v0_router = APIRouter()

# health
health_router = _health.router
v0_router.include_router(
    _health.router,
    tags=["diagnostics"],
)

# meta
v0_router.include_router(
    _meta.router,
    tags=["meta"],
    prefix="/meta",
)

# services
_SERVICE_PREFIX = "/services"
_SERVICE_TAGS: list[str | Enum] = [
    "services",
]
v0_router.include_router(
    _services_resources.router,
    tags=_SERVICE_TAGS,
    prefix=_SERVICE_PREFIX,
)
v0_router.include_router(
    _services_labels.router,
    tags=_SERVICE_TAGS,
    prefix=_SERVICE_PREFIX,
)
v0_router.include_router(
    _services_extras.router,
    tags=_SERVICE_TAGS,
    prefix=_SERVICE_PREFIX,
)
v0_router.include_router(
    _services_specifications.router,
    tags=_SERVICE_TAGS,
    prefix=_SERVICE_PREFIX,
)
v0_router.include_router(
    _services_ports.router,
    tags=_SERVICE_TAGS,
    prefix=_SERVICE_PREFIX,
)
v0_router.include_router(
    _services_access_rights.router,
    tags=_SERVICE_TAGS,
    prefix=_SERVICE_PREFIX,
)

# NOTE: that this router must come after resources/specifications/ports/access_rights
v0_router.include_router(
    _services.router,
    tags=_SERVICE_TAGS,
    prefix=_SERVICE_PREFIX,
)


def setup_rest_api_routes(app: FastAPI, vtag: str):
    # healthcheck at / and at /v0/
    app.include_router(health_router)
    # api under /v*
    app.include_router(v0_router, prefix=f"/{vtag}")
