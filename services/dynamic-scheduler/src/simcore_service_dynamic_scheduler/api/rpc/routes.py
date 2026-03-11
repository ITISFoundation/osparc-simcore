from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.api_schemas_dynamic_scheduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...services.rabbitmq import get_rabbitmq_rpc_client
from . import _services

ROUTERS: list[RPCRouter] = [
    _services.router,
]


async def rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
    rpc_client = get_rabbitmq_rpc_client(app)
    for router in ROUTERS:
        await rpc_client.register_router(router, DYNAMIC_SCHEDULER_RPC_NAMESPACE, app)

    yield {}
