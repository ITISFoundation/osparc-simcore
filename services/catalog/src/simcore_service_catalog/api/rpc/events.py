import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from models_library.api_schemas_catalog import CATALOG_RPC_NAMESPACE

from ...clients.rabbitmq import get_rabbitmq_rpc_server
from . import _services

_logger = logging.getLogger(__name__)


async def rpc_api_lifespan(app: FastAPI) -> AsyncIterator[State]:
    rpc_server = get_rabbitmq_rpc_server(app)
    await rpc_server.register_router(_services.router, CATALOG_RPC_NAMESPACE, app)
    try:
        yield {}
    finally:
        # No specific cleanup required for now
        pass
