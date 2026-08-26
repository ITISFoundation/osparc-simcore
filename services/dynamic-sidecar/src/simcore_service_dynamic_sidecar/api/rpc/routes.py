from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.rabbitmq_basic_types import RPCNamespace
from servicelib.rabbitmq import RPCRouter

from ...core.rabbitmq import get_rabbitmq_rpc_client
from ...core.settings import ApplicationSettings
from . import (
    _containers,
    _containers_extension,
    _containers_long_running_tasks,
    _disk,
    _disk_usage,
    _volumes,
)

ROUTERS: list[RPCRouter] = [
    _containers_extension.router,
    _containers_long_running_tasks.router,
    _containers.router,
    _disk_usage.router,
    _disk.router,
    _volumes.router,
]


async def _register_rpc_api_routes(app: FastAPI) -> None:
    rpc_client = get_rabbitmq_rpc_client(app)
    settings: ApplicationSettings = app.state.settings

    rpc_namespace = RPCNamespace.from_entries({"service": "dy-sidecar", "node_id": f"{settings.DY_SIDECAR_NODE_ID}"})
    for router in ROUTERS:
        await rpc_client.register_router(router, rpc_namespace, app)


async def _rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _register_rpc_api_routes(app)
    yield


def configure_rpc_api_routes(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_rpc_api_routes_lifespan)
