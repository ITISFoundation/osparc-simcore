import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any, NamedTuple

from aiohttp import web
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import ConsumerTag, ExchangeName, QueueName, RabbitMQClient
from servicelib.utils import logged_gather

from ..rabbitmq import get_rabbitmq_client

_logger = logging.getLogger(__name__)


class SubcribeArgumentsTuple(NamedTuple):
    exchange_name: str
    parser_fct: Callable[[web.Application, bytes], Coroutine[Any, Any, bool]]
    queue_kwargs: dict[str, Any]


async def subscribe_to_rabbitmq(
    app,
    exchange_to_parser_config: tuple[
        SubcribeArgumentsTuple,
        ...,
    ],
) -> dict[ExchangeName, tuple[QueueName, ConsumerTag]]:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channels"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queue_consumer_mappings = await logged_gather(
            *(
                rabbit_client.subscribe(
                    p.exchange_name,
                    functools.partial(p.parser_fct, app),
                    **p.queue_kwargs,
                )
                for p in exchange_to_parser_config
            ),
            reraise=True,
        )
    return {
        exchange_name: queue_consumer_map
        for (exchange_name, *_), queue_consumer_map in zip(
            exchange_to_parser_config, subscribed_queue_consumer_mappings, strict=True
        )
    }
