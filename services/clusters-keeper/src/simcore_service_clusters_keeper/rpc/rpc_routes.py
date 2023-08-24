import functools
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCMethodName

from ..modules.rabbitmq import (
    CLUSTERS_KEEPER_RPC_NAMESPACE,
    get_rabbitmq_rpc_client,
    is_rabbitmq_enabled,
)
from . import clusters
from .rpc_router import RPCRouter


async def _include_router(
    app: FastAPI, rpc_client: RabbitMQClient, router: RPCRouter
) -> None:
    for rpc_method_name, handler in router.routes.items():
        await rpc_client.rpc_register_handler(
            CLUSTERS_KEEPER_RPC_NAMESPACE,
            RPCMethodName(rpc_method_name),
            functools.partial(handler, app),
        )


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _start() -> None:
        if is_rabbitmq_enabled(app):
            rpc_client = get_rabbitmq_rpc_client(app)
            await _include_router(app, rpc_client, clusters.router)

    return _start


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        assert app  # nosec

    return _stop


def setup_rpc_routes(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
