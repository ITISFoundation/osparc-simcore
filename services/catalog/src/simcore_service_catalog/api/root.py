from fastapi import APIRouter

from .routes import dags, health, meta, registry, services

router = APIRouter()
router.include_router(health.router)

# API
router.include_router(meta.router, tags=["meta"], prefix="/meta")
router.include_router(dags.router, tags=["DAG"], prefix="/dags")
router.include_router(services.router, tags=["services"], prefix="/services")
router.include_router(registry.router, tags=["registry"], prefix="/registry")
