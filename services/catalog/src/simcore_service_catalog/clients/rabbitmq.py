import logging
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.fastapi.rabbitmq_lifespan import configure_rabbitmq_rpc_client
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings

from .._meta import PROJECT_NAME

_logger = logging.getLogger(__name__)


def configure_rabbitmq_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RabbitSettings,
) -> None:
    configure_rabbitmq_rpc_client(
        app_lifespan,
        settings=settings,
        client_name=f"{PROJECT_NAME}_rpc_client",
    )


def get_rabbitmq_rpc_client(app: FastAPI) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)
