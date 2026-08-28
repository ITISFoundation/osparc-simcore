import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter

from ...services.modules.rabbitmq import get_rabbitmq_rpc_client
from . import (
    _credit_transactions,
    _licensed_items_checkouts,
    _licensed_items_purchases,
    _pricing_plans,
    _service_runs,
)

_logger = logging.getLogger(__name__)


ROUTERS: list[RPCRouter] = [
    _credit_transactions.router,
    _service_runs.router,
    _pricing_plans.router,
    _licensed_items_purchases.router,
    _licensed_items_checkouts.router,
]


def configure_rpc_api_routes(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
        with log_context(
            _logger,
            logging.INFO,
            msg="RUT startup RPC API Routes",
        ):
            rpc_client = get_rabbitmq_rpc_client(app)
            for router in ROUTERS:
                await rpc_client.register_router(router, RESOURCE_USAGE_TRACKER_RPC_NAMESPACE, app)
        yield {}

    app_lifespan.add(_rpc_api_routes_lifespan)
