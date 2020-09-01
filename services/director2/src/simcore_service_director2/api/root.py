from fastapi import APIRouter

from .routes import services, health, meta

router = APIRouter()
router.include_router(health.router)

# API
router.include_router(meta.router, tags=["meta"], prefix="/meta")
router.include_router(services.router, tags=["services"], prefix="/services")
