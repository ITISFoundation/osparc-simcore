"""Free functions to inject dependencies in routes handlers"""

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ..domains.database.service import (
    PostgresHealth,
)
from ..domains.database.service import get_postgress_health as get_postgress_db_health


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_rabbitmq_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQRPCClient:
    assert isinstance(app.state.rabbitmq_rpc_server, RabbitMQRPCClient)  # nosec
    return app.state.rabbitmq_rpc_server


def get_postgress_health(
    app: Annotated[FastAPI, Depends(get_application)],
) -> PostgresHealth:
    return get_postgress_db_health(app)
