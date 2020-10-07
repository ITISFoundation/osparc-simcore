from fastapi import APIRouter

from .routes import health, meta, users, solvers, files

router = APIRouter()
router.include_router(health.router)

# API
router.include_router(meta.router, tags=["meta"], prefix="/meta")
router.include_router(users.router, tags=["users"], prefix="/me")
router.include_router(files.router, tags=["files"], prefix="/files")
router.include_router(solvers.router, tags=["solvers"], prefix="/solvers")
