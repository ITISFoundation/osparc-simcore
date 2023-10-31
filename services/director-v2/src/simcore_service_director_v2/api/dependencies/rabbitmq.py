from fastapi import Request
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient

from ...modules.rabbitmq import get_rabbitmq_rpc_client


def get_rabbitmq_client(request: Request) -> RabbitMQClient:
    assert type(request.app.state.rabbitmq_client) == RabbitMQClient  # nosec
    return request.app.state.rabbitmq_client


def rabbitmq_rpc_client(request: Request) -> RabbitMQRPCClient:
    return get_rabbitmq_rpc_client(request.app)
