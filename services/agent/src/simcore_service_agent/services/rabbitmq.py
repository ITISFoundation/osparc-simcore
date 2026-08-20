from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.rabbitmq import RabbitMQRPCClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings


def configure_rabbitmq(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _rabbitmq_lifespan(app: FastAPI) -> AsyncIterator[State]:
        settings: RabbitSettings = app.state.settings.AGENT_RABBITMQ
        app.state.rabbitmq_rpc_client = None
        await wait_till_rabbitmq_responsive(settings.dsn)

        app.state.rabbitmq_rpc_client = await RabbitMQRPCClient.create(
            client_name="dynamic_scheduler_rpc_client", settings=settings
        )
        try:
            yield {}
        finally:
            if app.state.rabbitmq_rpc_client:
                await app.state.rabbitmq_rpc_client.close()

    app_lifespan.add(_rabbitmq_lifespan)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)
