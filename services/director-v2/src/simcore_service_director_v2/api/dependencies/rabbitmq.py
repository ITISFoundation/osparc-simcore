from fastapi import Request
from servicelib.rabbitmq import RabbitMQRPCClient

from ...modules.rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client


def get_rabbitmq_client_from_request(request: Request):
    return get_rabbitmq_client(request.app)


def rabbitmq_rpc_client(request: Request) -> RabbitMQRPCClient:
    return get_rabbitmq_rpc_client(request.app)
