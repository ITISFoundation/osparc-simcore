import logging
from typing import cast

from fastapi import FastAPI
from fastapi.requests import Request
from servicelib.rabbitmq import (
    RabbitMQClient,
    RabbitMQRPCClient,
    wait_till_rabbitmq_responsive,
)
from settings_library.rabbit import RabbitSettings

from ...exceptions.errors import ConfigurationError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: RabbitSettings | None = (
            app.state.settings.RESOURCE_USAGE_TRACKER_RABBITMQ
        )
        if not settings:
            raise ConfigurationError(
                msg="Rabbit MQ client is de-activated in the settings"
            )
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="resource-usage-tracker", settings=settings
        )
        app.state.rabbitmq_rpc_server = await RabbitMQRPCClient.create(
            client_name="resource_usage_tracker_rpc_server", settings=settings
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()
        if app.state.rabbitmq_rpc_server:
            await app.state.rabbitmq_rpc_server.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client_from_request(request: Request):
    return get_rabbitmq_client(request.app)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_server(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_server  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_server)


__all__ = ("RabbitMQClient",)
