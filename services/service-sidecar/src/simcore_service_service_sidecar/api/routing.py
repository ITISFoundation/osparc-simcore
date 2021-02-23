# module acting as root for all routes

from fastapi import APIRouter

from .compose import compose_router
from .container import container_router
from .containers import containers_router
from .health import health_router
from .state import state_router
from .retrive import retrive_router
from .push import push_router

# setup and register all routes here form different modules
main_router = APIRouter()
main_router.include_router(health_router)
main_router.include_router(compose_router)
main_router.include_router(containers_router)
main_router.include_router(container_router)
main_router.include_router(state_router)
main_router.include_router(retrive_router)
main_router.include_router(push_router)

__all__ = ["main_router"]
