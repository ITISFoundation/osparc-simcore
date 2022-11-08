from fastapi import APIRouter

from .routes import (
    dags,
    health,
    meta,
    services,
    services_ports,
    services_resources,
    services_specifications,
)

router = APIRouter()
router.include_router(health.router)

# API
router.include_router(meta.router, tags=["meta"], prefix="/meta")
router.include_router(dags.router, tags=["DAG"], prefix="/dags")

SERVICE_PREFIX = "/services"
SERVICE_TAGS = [
    "services",
]

router.include_router(
    services_resources.router, tags=SERVICE_TAGS, prefix=SERVICE_PREFIX
)
router.include_router(
    services_specifications.router, tags=SERVICE_TAGS, prefix=SERVICE_PREFIX
)

router.include_router(services_ports.router, tags=SERVICE_TAGS, prefix=SERVICE_PREFIX)

# NOTE: that this router must come after resources/specifications/ports
router.include_router(services.router, tags=SERVICE_TAGS, prefix=SERVICE_PREFIX)
