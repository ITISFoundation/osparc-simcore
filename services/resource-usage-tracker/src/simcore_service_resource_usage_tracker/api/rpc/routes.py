from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from servicelib.rabbitmq import RPCRouter

from ...services.modules.rabbitmq import get_rabbitmq_rpc_server
from . import _resource_tracker

ROUTERS: list[RPCRouter] = [
    _resource_tracker.router,
]


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)
        for router in ROUTERS:
            await rpc_server.register_router(
                router, RESOURCE_USAGE_TRACKER_RPC_NAMESPACE, app
            )

    app.add_event_handler("startup", startup)
