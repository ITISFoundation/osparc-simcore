# pylint:disable=unused-import

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from servicelib.rabbitmq import RabbitMQRPCClient

from ...modules.postgres import PostgresLiveness
from ...modules.postgres import get_postgres_liveness as postgres_get_postgres_liveness


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_rabbitmq_rpc_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQRPCClient:
    assert isinstance(app.state.rabbitmq_rpc_client, RabbitMQRPCClient)  # nosec
    return app.state.rabbitmq_rpc_client


def get_postgres_liveness(
    app: Annotated[FastAPI, Depends(get_application)],
) -> PostgresLiveness:
    return postgres_get_postgres_liveness(app)
