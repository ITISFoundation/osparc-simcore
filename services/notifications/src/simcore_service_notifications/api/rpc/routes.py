from collections.abc import AsyncIterator

from celery_library.rpc import _async_jobs
from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.api_schemas_notifications import NOTIFICATIONS_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...clients.celery import get_task_manager_from_app
from ...clients.rabbitmq import get_rabbitmq_rpc_server
from . import _notifications

ROUTERS: list[RPCRouter] = [
    _async_jobs.router,
    _notifications.router,
]


async def rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
    rpc_server = get_rabbitmq_rpc_server(app)
    task_manager = get_task_manager_from_app(app)
    for router in ROUTERS:
        await rpc_server.register_router(
            router, NOTIFICATIONS_RPC_NAMESPACE, task_manager=task_manager
        )  # pragma: no cover

    yield {}
