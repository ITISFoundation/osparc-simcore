import functools
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any, Final, NamedTuple

from aiohttp import web
from models_library.rabbitmq_messages import InstrumentationRabbitMessage
from servicelib.aiohttp.monitor_services import (
    MONITOR_SERVICE_STARTED_LABELS,
    MONITOR_SERVICE_STOPPED_LABELS,
    service_started,
    service_stopped,
)
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import logged_gather

from ..rabbitmq import get_rabbitmq_client
from ._constants import APP_RABBITMQ_CONSUMERS_KEY

_logger = logging.getLogger(__name__)


async def _instrumentation_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = InstrumentationRabbitMessage.parse_raw(data)
    if rabbit_message.metrics == "service_started":
        service_started(
            app,
            **{
                key: rabbit_message.dict()[key]
                for key in MONITOR_SERVICE_STARTED_LABELS
            },
        )
    elif rabbit_message.metrics == "service_stopped":
        service_stopped(
            app,
            **{
                key: rabbit_message.dict()[key]
                for key in MONITOR_SERVICE_STOPPED_LABELS
            },
        )
    return True


class SubcribeArgumentsTuple(NamedTuple):
    exchange_name: str
    parser_fct: Callable[[web.Application, bytes], Coroutine[Any, Any, bool]]
    queue_kwargs: dict[str, Any]


_EXCHANGE_TO_PARSER_CONFIG: Final[tuple[SubcribeArgumentsTuple, ...,]] = (
    SubcribeArgumentsTuple(
        InstrumentationRabbitMessage.get_channel_name(),
        _instrumentation_message_parser,
        {"exclusive_queue": False},
    ),
)


async def _subscribe_to_rabbitmq(app) -> dict[str, str]:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channels"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queues = await logged_gather(
            *(
                rabbit_client.subscribe(
                    p.exchange_name,
                    functools.partial(p.parser_fct, app),
                    **p.queue_kwargs,
                )
                for p in _EXCHANGE_TO_PARSER_CONFIG
            ),
            reraise=False,
        )
    return {
        exchange_name: queue_name
        for (exchange_name, *_), queue_name in zip(
            _EXCHANGE_TO_PARSER_CONFIG, subscribed_queues, strict=True
        )
    }


async def _unsubscribe_from_rabbitmq(app) -> None:
    with log_context(
        _logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"
    ), log_catch(_logger, reraise=False):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await logged_gather(
            *(
                rabbit_client.unsubscribe_consumer(queue_name)
                for queue_name in app[APP_RABBITMQ_CONSUMERS_KEY].values()
            ),
        )


async def on_cleanup_ctx_rabbitmq_consumers(
    app: web.Application,
) -> AsyncIterator[None]:
    app[APP_RABBITMQ_CONSUMERS_KEY] = await _subscribe_to_rabbitmq(app)
    yield

    # cleanup
    await _unsubscribe_from_rabbitmq(app)
