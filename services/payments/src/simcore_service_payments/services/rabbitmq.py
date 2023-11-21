import logging
from typing import cast

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitMessageBase
from servicelib.rabbitmq import (
    RabbitMQClient,
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

_logger = logging.getLogger(__name__)


def setup_rabbitmq(app: FastAPI) -> None:
    settings: RabbitSettings = app.state.settings.PAYMENTS_RABBITMQ
    app.state.rabbitmq_client = None
    app.state.rabbitmq_rpc_server = None

    async def _on_startup() -> None:
        await wait_till_rabbitmq_responsive(settings.dsn)

        app.state.rabbitmq_client = RabbitMQClient(
            client_name="payments", settings=settings
        )
        app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
            client_name="payments_rpc_server", settings=settings
        )
        app.state.rabbitmq_rpc_client = await RabbitMQRPCClient.create(
            client_name="payments_rpc_client", settings=settings
        )

    async def _on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()
            app.state.rabbitmq_client = None
        if app.state.rabbitmq_rpc_server:
            await app.state.rabbitmq_rpc_server.close()
            app.state.rabbitmq_rpc_server = None
        if app.state.rabbitmq_rpc_client:
            await app.state.rabbitmq_rpc_client.close()
            app.state.rabbitmq_rpc_client = None

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_server  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    await get_rabbitmq_client(app).publish(message.channel_name, message)
