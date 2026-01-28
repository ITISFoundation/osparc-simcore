from collections.abc import Awaitable, Callable

from fastapi import FastAPI
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


def setup_rpc_routes(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
