from fastapi import APIRouter

from .routes import health, meta, running_interactive, services

meta_router = APIRouter()
meta_router.include_router(health.router)
meta_router.include_router(meta.router, prefix="/meta")


# Legacy
v0_router = APIRouter()
v0_router.include_router(services.router, tags=["services"], prefix="/services")
v0_router.include_router(
    running_interactive.router,
    tags=["services"],
    prefix="/running_interactive_services",
)

# Latest API
v2_router = APIRouter()
v2_router.include_router(meta.router, tags=["demo"], prefix="/demo")


__all__ = ["v0_router", "v2_router", "meta_router"]
