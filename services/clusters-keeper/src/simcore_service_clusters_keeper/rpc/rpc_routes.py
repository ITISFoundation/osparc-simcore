from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE

from ..modules.rabbitmq import get_rabbitmq_rpc_client, is_rabbitmq_enabled
from .clusters import router as clusters_router
from .ec2_instances import router as ec2_instances_router


async def _rpc_routes_lifespan(app: FastAPI) -> AsyncIterator[State]:
    if is_rabbitmq_enabled(app):
        rpc_client = get_rabbitmq_rpc_client(app)
        for router in [clusters_router, ec2_instances_router]:
            await rpc_client.register_router(router, CLUSTERS_KEEPER_RPC_NAMESPACE, app)

    yield {}


def configure_rpc_routes(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_rpc_routes_lifespan)
