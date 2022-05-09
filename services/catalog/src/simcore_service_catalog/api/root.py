from fastapi import APIRouter

from .routes import (
    dags,
    health,
    meta,
    services,
    services_resources,
    services_specifications,
)

router = APIRouter()
router.include_router(health.router)

# API
router.include_router(meta.router, tags=["meta"], prefix="/meta")
router.include_router(dags.router, tags=["DAG"], prefix="/dags")
router.include_router(services_resources.router, tags=["services"], prefix="/services")
router.include_router(
    services_specifications.router, tags=["services"], prefix="/services"
)
# note that this router must come after resources/specifications
router.include_router(services.router, tags=["services"], prefix="/services")
