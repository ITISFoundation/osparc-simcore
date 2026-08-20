import logging
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi_lifespan_manager import LifespanManager, State
from models_library.rabbitmq_messages import RabbitMessageBase
from servicelib.rabbitmq import (
    RabbitMQClient,
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

_logger = logging.getLogger(__name__)


def get_rabbitmq_settings(app: FastAPI) -> RabbitSettings:
    settings: RabbitSettings = app.state.settings.PAYMENTS_RABBITMQ
    return settings


def configure_rabbitmq(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _rabbitmq_lifespan(app: FastAPI) -> AsyncIterator[State]:
        settings: RabbitSettings = get_rabbitmq_settings(app)
        app.state.rabbitmq_client = None
        app.state.rabbitmq_rpc_client = None
        await wait_till_rabbitmq_responsive(settings.dsn)

        app.state.rabbitmq_client = RabbitMQClient(client_name="payments", settings=settings)
        app.state.rabbitmq_rpc_client = await RabbitMQRPCClient.create(
            client_name="payments_rpc_client", settings=settings
        )
        try:
            yield {}
        finally:
            if app.state.rabbitmq_client:
                await app.state.rabbitmq_client.close()
                app.state.rabbitmq_client = None
            if app.state.rabbitmq_rpc_client:
                await app.state.rabbitmq_rpc_client.close()
                app.state.rabbitmq_rpc_client = None

    app_lifespan.add(_rabbitmq_lifespan)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_client_from_request(request: Request) -> RabbitMQClient:
    return get_rabbitmq_client(request.app)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)


def get_rabbitmq_rpc_client_from_request(request: Request) -> RabbitMQRPCClient:
    return get_rabbitmq_rpc_client(request.app)


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    await get_rabbitmq_client(app).publish(message.channel_name, message)
