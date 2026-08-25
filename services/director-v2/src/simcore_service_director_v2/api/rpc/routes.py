import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.api_schemas_directorv2 import (
    DIRECTOR_V2_RPC_NAMESPACE,
)
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter

from ...modules.rabbitmq import get_rabbitmq_rpc_client
from . import _computations, _computations_tasks

_logger = logging.getLogger(__name__)


ROUTERS: list[RPCRouter] = [_computations.router, _computations_tasks.router]


async def _rpc_api_routes_lifespan(app: FastAPI) -> AsyncIterator[None]:
    with log_context(
        _logger,
        logging.INFO,
        msg="Director-v2 startup RPC API Routes",
    ):
        rpc_client = get_rabbitmq_rpc_client(app)
        for router in ROUTERS:
            await rpc_client.register_router(router, DIRECTOR_V2_RPC_NAMESPACE, app)
    yield


def configure_rpc_api_routes(app_lifespan: LifespanManager) -> None:
    app_lifespan.add(_rpc_api_routes_lifespan)
