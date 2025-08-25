import logging

from fastapi import FastAPI
from models_library.api_schemas_directorv2 import (
    DIRECTOR_V2_RPC_NAMESPACE,
)
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter

from ...modules.rabbitmq import get_rabbitmq_rpc_server
from . import _computations, _computations_tasks

_logger = logging.getLogger(__name__)


ROUTERS: list[RPCRouter] = [_computations.router, _computations_tasks.router]


def setup_rpc_api_routes(app: FastAPI) -> None:
    async def startup() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="Director-v2 startup RPC API Routes",
        ):
            rpc_server = get_rabbitmq_rpc_server(app)
            for router in ROUTERS:
                await rpc_server.register_router(router, DIRECTOR_V2_RPC_NAMESPACE, app)

    app.add_event_handler("startup", startup)
