from typing import cast

from fastapi import FastAPI, Request
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_client,
    configure_rabbitmq_rpc_client,
)
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient

from ...exceptions.errors import ConfigurationError


def configure_rabbitmq(app: FastAPI, app_lifespan: LifespanManager[FastAPI]) -> None:
    settings = app.state.settings.RESOURCE_USAGE_TRACKER_RABBITMQ
    if not settings:
        raise ConfigurationError(msg="Rabbit MQ client is de-activated in the settings")

    configure_rabbitmq_client(
        app_lifespan,
        settings=settings,
        client_name="resource-usage-tracker",
        wait_for_connectivity=True,
    )
    configure_rabbitmq_rpc_client(
        app_lifespan,
        settings=settings,
        client_name="resource_usage_tracker_rpc_client",
        wait_for_connectivity=False,
    )


def get_rabbitmq_client_from_request(request: Request):
    return get_rabbitmq_client(request.app)


def get_rabbitmq_rpc_client_from_request(request: Request) -> RabbitMQRPCClient:
    return get_rabbitmq_rpc_client(request.app)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(msg="RabbitMQ client is not available. Please check the configuration.")
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)


__all__ = ("RabbitMQClient",)
