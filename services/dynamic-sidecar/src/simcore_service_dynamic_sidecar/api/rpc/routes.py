from fastapi import FastAPI
from models_library.rabbitmq_basic_types import RPCNamespace
from servicelib.rabbitmq import RPCRouter

from ...core.rabbitmq import get_rabbitmq_rpc_server
from ...core.settings import ApplicationSettings
from . import _disk, _disk_usage, _volumes

ROUTERS: list[RPCRouter] = [
    _disk_usage.router,
    _disk.router,
    _volumes.router,
]


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)
        settings: ApplicationSettings = app.state.settings

        rpc_namespace = RPCNamespace.from_entries(
            {"service": "dy-sidecar", "node_id": f"{settings.DY_SIDECAR_NODE_ID}"}
        )
        for router in ROUTERS:
            await rpc_server.register_router(router, rpc_namespace, app)

    app.add_event_handler("startup", startup)
