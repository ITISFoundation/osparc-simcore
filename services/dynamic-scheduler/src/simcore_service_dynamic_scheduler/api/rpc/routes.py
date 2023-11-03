from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE
from servicelib.rabbitmq import RPCRouter

from ...services.rabbitmq import get_rabbitmq_rpc_server

ROUTERS: list[RPCRouter] = []


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def _on_startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)
        for router in ROUTERS:
            await rpc_server.register_router(
                router, DYNAMIC_SCHEDULER_RPC_NAMESPACE, app
            )

    app.add_event_handler("startup", _on_startup)
