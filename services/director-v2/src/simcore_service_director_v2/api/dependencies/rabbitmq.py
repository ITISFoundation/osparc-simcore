from fastapi import Request
from servicelib.rabbitmq import RabbitMQClient


def get_rabbitmq_client(request: Request) -> RabbitMQClient:
    assert type(request.app.state.rabbitmq_client) == RabbitMQClient  # nosec
    return request.app.state.rabbitmq_client
