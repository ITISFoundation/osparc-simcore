import logging
from typing import cast

from fastapi import FastAPI
from servicelib.rabbitmq import (
    RabbitMQClient,
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

from ...exceptions.custom_errors import ApplicationSetupError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: RabbitSettings | None = app.state.settings.EFS_GUARDIAN_RABBITMQ
        if not settings:
            raise ApplicationSetupError(
                msg="Rabbit MQ client is de-activated in the settings"
            )
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="efs-guardian", settings=settings
        )
        app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
            client_name="efs_guardian_rpc_server", settings=settings
        )
        app.state.rabbitmq_rpc_client = await RabbitMQRPCClient.create(
            client_name="efs_guardian_rpc_client", settings=settings
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()
        if app.state.rabbitmq_rpc_server:
            await app.state.rabbitmq_rpc_server.close()
        if app.state.rabbitmq_rpc_client:
            await app.state.rabbitmq_rpc_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ApplicationSetupError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_server  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)


__all__ = ("RabbitMQClient",)
