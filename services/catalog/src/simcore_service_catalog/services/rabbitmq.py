import logging
from typing import cast

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQRPCClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from .._meta import PROJECT_NAME

_logger = logging.getLogger(__name__)


def get_rabbitmq_settings(app: FastAPI) -> RabbitSettings:
    settings: RabbitSettings = app.state.settings.CATALOG_RABBITMQ
    return settings


def setup_rabbitmq(app: FastAPI) -> None:
    settings: RabbitSettings = get_rabbitmq_settings(app)
    app.state.rabbitmq_rpc_server = None

    async def _on_startup() -> None:
        await wait_till_rabbitmq_responsive(settings.dsn)

        app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
            client_name=f"{PROJECT_NAME}_rpc_server", settings=settings
        )

    async def _on_shutdown() -> None:
        if app.state.rabbitmq_rpc_server:
            await app.state.rabbitmq_rpc_server.close()
            app.state.rabbitmq_rpc_server = None

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_server  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)
