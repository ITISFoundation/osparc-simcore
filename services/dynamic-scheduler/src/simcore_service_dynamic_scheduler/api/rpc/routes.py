from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.api_schemas_dynamic_scheduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...services.rabbitmq import get_rabbitmq_rpc_server
from . import _services

ROUTERS: list[RPCRouter] = [
    _services.router,
]


async def lifespan_rpc_api_routes(app: FastAPI) -> AsyncIterator[State]:
    rpc_server = get_rabbitmq_rpc_server(app)
    for router in ROUTERS:
        await rpc_server.register_router(router, DYNAMIC_SCHEDULER_RPC_NAMESPACE, app)

    yield {}
