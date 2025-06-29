import logging
from typing import Final

from aiohttp import web
from models_library.projects import ProjectID
from models_library.rabbitmq_messages import (
    ComputationalPipelineStatusMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    RabbitMessageBase,
)
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RabbitMQClient

from ..rabbitmq import get_rabbitmq_client

_logger = logging.getLogger(__name__)


_SUBSCRIBABLE_EXCHANGES: Final[list[type[RabbitMessageBase]]] = [
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ComputationalPipelineStatusMessage,
]


async def subscribe(app: web.Application, project_id: ProjectID) -> None:
    rabbit_client: RabbitMQClient = get_rabbitmq_client(app)

    for exchange in _SUBSCRIBABLE_EXCHANGES:
        exchange_name = exchange.get_channel_name()
        await rabbit_client.add_topics(exchange_name, topics=[f"{project_id}.*"])


async def unsubscribe(app: web.Application, project_id: ProjectID) -> None:
    rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
    for exchange in _SUBSCRIBABLE_EXCHANGES:
        exchange_name = exchange.get_channel_name()
        with log_catch(_logger, reraise=False):
            # NOTE: in case something bad happenned with the connection to the RabbitMQ server
            # such as a network disconnection. this call can fail.
            await rabbit_client.remove_topics(exchange_name, topics=[f"{project_id}.*"])
