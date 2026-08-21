from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_client,
    configure_rabbitmq_rpc_client,
)
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient

from ...exceptions.custom_errors import ApplicationSetupError


def configure_rabbitmq(app: FastAPI, app_lifespan: LifespanManager[FastAPI]) -> None:
    settings = app.state.settings.EFS_GUARDIAN_RABBITMQ
    if not settings:
        raise ApplicationSetupError(msg="Rabbit MQ client is de-activated in the settings")

    configure_rabbitmq_client(
        app_lifespan,
        settings=settings,
        client_name="efs-guardian",
        wait_for_connectivity=True,
    )
    configure_rabbitmq_rpc_client(
        app_lifespan,
        settings=settings,
        client_name="efs_guardian_rpc_client",
        wait_for_connectivity=False,
    )


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ApplicationSetupError(msg="RabbitMQ client is not available. Please check the configuration.")
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)


__all__ = ("RabbitMQClient",)
