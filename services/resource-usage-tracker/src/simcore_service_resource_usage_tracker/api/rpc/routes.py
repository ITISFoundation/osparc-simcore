import logging

from fastapi import FastAPI
from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter

from ...services.modules.rabbitmq import get_rabbitmq_rpc_server
from . import _licensed_items_checkouts, _licensed_items_purchases, _resource_tracker

_logger = logging.getLogger(__name__)


ROUTERS: list[RPCRouter] = [
    _resource_tracker.router,
    _licensed_items_purchases.router,
    _licensed_items_checkouts.router,
]


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def startup() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="RUT startup RPC API Routes",
        ):
            rpc_server = get_rabbitmq_rpc_server(app)
            for router in ROUTERS:
                await rpc_server.register_router(
                    router, RESOURCE_USAGE_TRACKER_RPC_NAMESPACE, app
                )

    app.add_event_handler("startup", startup)
