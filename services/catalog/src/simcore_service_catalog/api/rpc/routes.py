import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.api_schemas_catalog import CATALOG_RPC_NAMESPACE

from ...infrastructure.rabbitmq import get_rabbitmq_rpc_server
from . import _services

_logger = logging.getLogger(__name__)


async def setup_rpc_api_routes(app: FastAPI) -> AsyncIterator[State]:
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(_services.router, CATALOG_RPC_NAMESPACE, app)

    yield {}
