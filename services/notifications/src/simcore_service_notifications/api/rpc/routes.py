from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.notifications.rpc import NOTIFICATIONS_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...clients.rabbitmq import get_rabbitmq_rpc_client
from . import _notifications

ROUTERS: list[RPCRouter] = [
    _notifications.router,
]


async def rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
    rpc_client = get_rabbitmq_rpc_client(app)

    for router in ROUTERS:
        await rpc_client.register_router(router, NOTIFICATIONS_RPC_NAMESPACE, app)  # pragma: no cover

    yield {}
