from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_client as _configure_rabbitmq_client,
)
from servicelib.fastapi.rabbitmq_lifespan import (
    configure_rabbitmq_rpc_client as _configure_rabbitmq_rpc_client,
)
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings


def configure_rabbitmq_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RabbitSettings,
) -> None:
    _configure_rabbitmq_client(
        app_lifespan,
        settings=settings,
        client_name="dynamic_scheduler",
        wait_for_connectivity=True,
    )
    _configure_rabbitmq_rpc_client(
        app_lifespan,
        settings=settings,
        client_name="dynamic_scheduler_rpc_client",
        wait_for_connectivity=False,
    )


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)
