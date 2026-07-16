from enum import Enum
from functools import cache

from fastapi import APIRouter, FastAPI

from ..._meta import (
    API_VTAG,
)
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

_SERVICE_PREFIX = "/services"
_SERVICE_TAGS: list[str | Enum] = [
    "services",
]


@cache
def setup_rest_api_routes(app: FastAPI) -> None:
    # healthcheck at / and at /v0/
    health_router = _health.router
    app.include_router(health_router)

    # api under /v*
    v0_router = APIRouter(prefix=f"/{API_VTAG}")
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

    app.include_router(
        v0_router,
    )
