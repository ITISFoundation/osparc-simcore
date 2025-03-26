"""Free functions to inject dependencies in routes handlers"""

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_rabbitmq_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQRPCClient:
    assert isinstance(app.state.rabbitmq_rpc_server, RabbitMQRPCClient)  # nosec
    return app.state.rabbitmq_rpc_server
