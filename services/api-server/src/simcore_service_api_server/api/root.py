from fastapi import APIRouter

from .routes import health, meta, users

router = APIRouter()
router.include_router(health.router)
router.include_router(meta.router, tags=["meta"], prefix="/meta")
router.include_router(users.router, tags=["users"], prefix="/me")
