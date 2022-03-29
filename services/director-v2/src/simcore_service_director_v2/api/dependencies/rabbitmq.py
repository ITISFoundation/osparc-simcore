from fastapi import Request

from ...modules.rabbitmq import RabbitMQClient


def get_rabbitmq_client(request: Request) -> RabbitMQClient:
    return request.app.state.rabbitmq_client
