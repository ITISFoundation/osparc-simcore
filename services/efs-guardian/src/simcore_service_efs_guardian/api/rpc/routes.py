from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.api_schemas_efs_guardian import EFS_GUARDIAN_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...services.modules.rabbitmq import get_rabbitmq_rpc_client
from . import _efs_guardian

ROUTERS: list[RPCRouter] = [
    _efs_guardian.router,
]


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _start() -> None:
        rpc_client = get_rabbitmq_rpc_client(app)
        for router in ROUTERS:
            await rpc_client.register_router(router, EFS_GUARDIAN_RPC_NAMESPACE, app)

    return _start


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        assert app  # nosec

    return _stop


def configure_rpc_routes(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _rpc_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
        try:
            await on_app_startup(app)()
            yield {}
        finally:
            await on_app_shutdown(app)()

    app_lifespan.add(_rpc_routes_lifespan)
