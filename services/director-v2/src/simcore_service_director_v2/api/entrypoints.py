from fastapi import APIRouter

from ..meta import api_vtag
from .routes import computations, health, meta, running_interactive, services

# Info
meta_router = APIRouter()
meta_router.include_router(health.router)
meta_router.include_router(meta.router, prefix="/meta")

# API v0 (Legacy)
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
v2_router.include_router(
    computations.router, tags=["computations"], prefix="/computations"
)

# root
api_router = APIRouter()
api_router.include_router(meta_router)
api_router.include_router(v0_router, prefix="/v0")
api_router.include_router(v2_router, prefix=f"/{api_vtag}")

__all__ = ["api_router"]
