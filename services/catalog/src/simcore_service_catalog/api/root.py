from enum import Enum

from fastapi import APIRouter

from .routes import (
    health,
    meta,
    services,
    services_access_rights,
    services_ports,
    services_resources,
    services_specifications,
)

router = APIRouter()
router.include_router(health.router)

# API
router.include_router(meta.router, tags=["meta"], prefix="/meta")

_SERVICE_PREFIX = "/services"
_SERVICE_TAGS: list[str | Enum] = [
    "services",
]


router.include_router(
    services_resources.router, tags=_SERVICE_TAGS, prefix=_SERVICE_PREFIX
)
router.include_router(
    services_specifications.router, tags=_SERVICE_TAGS, prefix=_SERVICE_PREFIX
)

router.include_router(services_ports.router, tags=_SERVICE_TAGS, prefix=_SERVICE_PREFIX)

router.include_router(
    services_access_rights.router, tags=_SERVICE_TAGS, prefix=_SERVICE_PREFIX
)

# NOTE: that this router must come after resources/specifications/ports/access_rights
router.include_router(services.router, tags=_SERVICE_TAGS, prefix=_SERVICE_PREFIX)
