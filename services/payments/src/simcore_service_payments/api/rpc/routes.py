import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.api_schemas_payments import PAYMENTS_RPC_NAMESPACE

from ...services.rabbitmq import get_rabbitmq_rpc_client
from . import _payments, _payments_methods

_logger = logging.getLogger(__name__)


def configure_rpc_api_routes(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
        rpc_client = get_rabbitmq_rpc_client(app)
        for router in (
            _payments.router,
            _payments_methods.router,
        ):
            await rpc_client.register_router(router, PAYMENTS_RPC_NAMESPACE, app)
        yield {}

    app_lifespan.add(_rpc_api_routes_lifespan)
