import logging
from collections.abc import AsyncIterator
from typing import Final

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
from ._rabbitmq_consumers_common import SubcribeArgumentsTuple, subscribe_to_rabbitmq

_logger = logging.getLogger(__name__)

_APP_RABBITMQ_CONSUMERS_KEY: Final[str] = f"{__name__}.rabbit_consumers"


async def _instrumentation_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = InstrumentationRabbitMessage.model_validate_json(data)
    if rabbit_message.metrics == "service_started":
        service_started(
            app,
            **{
                key: rabbit_message.model_dump()[key]
                for key in MONITOR_SERVICE_STARTED_LABELS
            },
        )
    elif rabbit_message.metrics == "service_stopped":
        service_stopped(
            app,
            **{
                key: rabbit_message.model_dump()[key]
                for key in MONITOR_SERVICE_STOPPED_LABELS
            },
        )
    return True


_EXCHANGE_TO_PARSER_CONFIG: Final[tuple[SubcribeArgumentsTuple, ...,]] = (
    SubcribeArgumentsTuple(
        InstrumentationRabbitMessage.get_channel_name(),
        _instrumentation_message_parser,
        {"exclusive_queue": False},
    ),
)


async def _unsubscribe_from_rabbitmq(app) -> None:
    with log_context(
        _logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"
    ), log_catch(_logger, reraise=False):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await logged_gather(
            *(
                rabbit_client.unsubscribe_consumer(*queue_consumer_map)
                for queue_consumer_map in app[_APP_RABBITMQ_CONSUMERS_KEY].values()
            ),
        )


async def on_cleanup_ctx_rabbitmq_consumers(
    app: web.Application,
) -> AsyncIterator[None]:
    app[_APP_RABBITMQ_CONSUMERS_KEY] = await subscribe_to_rabbitmq(
        app, _EXCHANGE_TO_PARSER_CONFIG
    )
    yield

    # cleanup
    await _unsubscribe_from_rabbitmq(app)
