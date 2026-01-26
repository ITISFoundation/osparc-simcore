# pylint:disable=unused-import

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from servicelib.rabbitmq import RabbitMQRPCClient

from ...clients.postgres import PostgresLiveness
from ...clients.postgres import get_postgres_liveness as _get_db_liveness
from ...templates import models as context_models  # noqa: F401 # NOTE: registers context models


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_rabbitmq_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQRPCClient:
    assert isinstance(app.state.rabbitmq_rpc_server, RabbitMQRPCClient)  # nosec
    return app.state.rabbitmq_rpc_server


def get_postgres_liveness(
    app: Annotated[FastAPI, Depends(get_application)],
) -> PostgresLiveness:
    return _get_db_liveness(app)
