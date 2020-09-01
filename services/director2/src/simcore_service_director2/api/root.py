from fastapi import APIRouter

from .routes import health, meta, running_interactive, services

router = APIRouter()
router.include_router(health.router)

# API
router.include_router(meta.router, tags=["meta"], prefix="/meta")
router.include_router(services.router, tags=["services"], prefix="/services")
router.include_router(
    running_interactive.router,
    tags=["services"],
    prefix="/running_interactive_services",
)
