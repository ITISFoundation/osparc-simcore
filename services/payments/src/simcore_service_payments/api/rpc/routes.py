import logging
from typing import Final

from fastapi import FastAPI
from pydantic import parse_obj_as
from servicelib.rabbitmq import RPCNamespace

from ...services.rabbitmq import get_rabbitmq_rpc_client, is_rabbitmq_enabled
from . import _payments

_logger = logging.getLogger(__name__)

PAYMENTS_RPC_NAMESPACE: Final[RPCNamespace] = parse_obj_as(RPCNamespace, "payments")


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def _on_startup() -> None:
        if is_rabbitmq_enabled(app):
            rpc_client = get_rabbitmq_rpc_client(app)
            await rpc_client.register_router(
                _payments.router, PAYMENTS_RPC_NAMESPACE, app
            )

    app.add_event_handler("startup", _on_startup)
