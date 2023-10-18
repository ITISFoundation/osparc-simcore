import logging

from fastapi import FastAPI
from models_library.api_schemas_payments import PAYMENTS_RPC_NAMESPACE

from ...services.rabbitmq import get_rabbitmq_rpc_server
from . import _payments

_logger = logging.getLogger(__name__)


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def _on_startup() -> None:
        rpc_server = get_rabbitmq_rpc_server(app)
        await rpc_server.register_router(_payments.router, PAYMENTS_RPC_NAMESPACE, app)

    app.add_event_handler("startup", _on_startup)
