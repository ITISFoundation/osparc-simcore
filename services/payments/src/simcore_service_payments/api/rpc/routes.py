from collections.abc import Awaitable, Callable

from fastapi import FastAPI

from ...services.rabbitmq import (
    PAYMENTS_RPC_NAMESPACE,
    get_rabbitmq_rpc_client,
    is_rabbitmq_enabled,
)
from . import _payments


def _create_on_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _start() -> None:
        if is_rabbitmq_enabled(app):
            rpc_client = get_rabbitmq_rpc_client(app)
            await rpc_client.register_router(
                _payments.router, PAYMENTS_RPC_NAMESPACE, app
            )

    return _start


def setup_rpc_routes(app: FastAPI) -> None:
    app.add_event_handler("startup", _create_on_startup(app))
