from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.api_schemas_notifications import NOTIFICATIONS_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...clients.rabbitmq import get_rabbitmq_rpc_server

ROUTERS: list[RPCRouter] = [
    # import and use all routers here
]


async def rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
    rpc_server = get_rabbitmq_rpc_server(app)

    for router in ROUTERS:
        await rpc_server.register_router(
            router, NOTIFICATIONS_RPC_NAMESPACE, app
        )  # pragma: no cover

    yield {}
