from fastapi import FastAPI
from models_library.api_schemas_notifications import NOTIFICATIONS_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...services.rabbitmq import get_rabbitmq_rpc_server

ROUTERS: list[RPCRouter] = [
    #  `_internal_module.router``
]


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)

        for router in ROUTERS:
            await rpc_server.register_router(router, NOTIFICATIONS_RPC_NAMESPACE, app)

    app.add_event_handler("startup", startup)
