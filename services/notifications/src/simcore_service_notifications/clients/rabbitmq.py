from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.rabbitmq import RabbitMQRPCClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from ..core.settings import ApplicationSettings


async def rabbitmq_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    rabbit_settings: RabbitSettings = settings.NOTIFICATIONS_RABBITMQ
    app.state.rabbitmq_rpc_server = None

    await wait_till_rabbitmq_responsive(rabbit_settings.dsn)

    app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
        client_name="notifications_rpc_server", settings=rabbit_settings
    )

    yield {}

    await app.state.rabbitmq_rpc_server.close()


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_server  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)
