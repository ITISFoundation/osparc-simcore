from fastapi import FastAPI
from models_library.api_schemas_dynamic_schduler import DYNAMIC_SCHEDULER_RPC_NAMESPACE

from ...services.rabbitmq import get_rabbitmq_rpc_server


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def _on_startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)
        for router in ():
            await rpc_server.register_router(
                router, DYNAMIC_SCHEDULER_RPC_NAMESPACE, app
            )

    app.add_event_handler("startup", _on_startup)
