from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar import DYNAMIC_SIDECAR_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...core.rabbitmq import get_rabbitmq_rpc_server
from . import _disk_usage

ROUTERS: list[RPCRouter] = [
    _disk_usage.router,
]


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)
        for router in ROUTERS:
            await rpc_server.register_router(router, DYNAMIC_SIDECAR_RPC_NAMESPACE, app)

    app.add_event_handler("startup", startup)
