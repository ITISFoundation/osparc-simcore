import logging
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.rabbitmq import RabbitMQRPCClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from .._meta import PROJECT_NAME

_logger = logging.getLogger(__name__)


def get_rabbitmq_settings(app: FastAPI) -> RabbitSettings:
    settings: RabbitSettings = app.state.settings.CATALOG_RABBITMQ
    return settings


async def rabbitmq_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: RabbitSettings = get_rabbitmq_settings(app)
    await wait_till_rabbitmq_responsive(settings.dsn)

    app.state.rabbitmq_rpc_client = await RabbitMQRPCClient.create(
        client_name=f"{PROJECT_NAME}_rpc_client", settings=settings
    )

    try:
        yield {}
    finally:
        if app.state.rabbitmq_rpc_client:
            await app.state.rabbitmq_rpc_client.close()
            app.state.rabbitmq_rpc_client = None


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)
