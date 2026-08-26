from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitMessageBase

from ..rabbitmq import RabbitMQClient
from .errors import ApplicationStateError


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ApplicationStateError(
            state="rabbitmq_client",
            msg="Rabbitmq service unavailable. Check app settings",
        )
    rabbitmq_client = app.state.rabbitmq_client
    assert isinstance(rabbitmq_client, RabbitMQClient)
    return rabbitmq_client


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    await get_rabbitmq_client(app).publish(message.channel_name, message)
