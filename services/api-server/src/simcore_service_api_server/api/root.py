from fastapi import APIRouter

from .routes import health, meta, users

router = APIRouter()
router.include_router(health.router)
router.include_router(meta.router, tags=["meta"], prefix="/meta")

# TODO: keeps for oauth or apikey schemes
# router.include_router(authentication.router, tags=["authentication"], prefix="/users")

router.include_router(users.router, tags=["users"], prefix="/me")

## TODO: disables studies for the moment
# router.include_router(studies.router, tags=["studies"], prefix="/studies")
