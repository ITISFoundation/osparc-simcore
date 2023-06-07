from aiohttp import web
from models_library.projects import ProjectID
from models_library.rabbitmq_messages import (
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
)
from servicelib.rabbitmq import RabbitMQClient

from ..rabbitmq import get_rabbitmq_client
from ._constants import APP_RABBITMQ_CONSUMERS_KEY


def _get_queue_name_from_exchange_name(app: web.Application, exchange_name: str) -> str:
    exchange_to_queues = app[APP_RABBITMQ_CONSUMERS_KEY]
    queue_name: str = exchange_to_queues[exchange_name]
    return queue_name


_SUBSCRIBABLE_EXCHANGES = [
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
]


async def subscribe(app: web.Application, project_id: ProjectID) -> None:
    rabbit_client: RabbitMQClient = get_rabbitmq_client(app)

    for exchange in _SUBSCRIBABLE_EXCHANGES:
        exchange_name = exchange.get_channel_name()
        queue_name = _get_queue_name_from_exchange_name(app, exchange_name)
        await rabbit_client.add_topics(
            exchange_name, queue_name, topics=[f"{project_id}.*"]
        )


async def unsubscribe(app: web.Application, project_id: ProjectID) -> None:
    rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
    for exchange in _SUBSCRIBABLE_EXCHANGES:
        exchange_name = exchange.get_channel_name()
        queue_name = _get_queue_name_from_exchange_name(app, exchange_name)
        await rabbit_client.remove_topics(
            exchange_name, queue_name, topics=[f"{project_id}.*"]
        )
