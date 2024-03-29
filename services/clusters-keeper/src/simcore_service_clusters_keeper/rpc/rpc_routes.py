from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE

from ..modules.rabbitmq import get_rabbitmq_rpc_client, is_rabbitmq_enabled
from .clusters import router as clusters_router
from .ec2_instances import router as ec2_instances_router


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _start() -> None:
        if is_rabbitmq_enabled(app):
            rpc_client = get_rabbitmq_rpc_client(app)
            for router in [clusters_router, ec2_instances_router]:
                await rpc_client.register_router(
                    router, CLUSTERS_KEEPER_RPC_NAMESPACE, app
                )

    return _start


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        assert app  # nosec

    return _stop


def setup_rpc_routes(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
