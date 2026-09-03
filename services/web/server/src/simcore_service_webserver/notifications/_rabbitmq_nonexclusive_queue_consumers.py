import logging
from collections.abc import AsyncIterator
from typing import Final

from aiohttp import web
from models_library.rabbitmq_messages import InstrumentationRabbitMessage, NodeDataUpdatedEventMessage
from servicelib.aiohttp.monitor_services import (
    MONITOR_SERVICE_STARTED_LABELS,
    MONITOR_SERVICE_STOPPED_LABELS,
    service_started,
    service_stopped,
)
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import ConsumerTag, ExchangeName, QueueName, RabbitMQClient
from servicelib.utils import logged_gather

from ..db_listener._node_update_handler import apply_node_data_update
from ..rabbitmq import get_rabbitmq_client
from ._rabbitmq_consumers_common import SubscribeArgumentsTuple, subscribe_to_rabbitmq

_logger = logging.getLogger(__name__)

_APP_RABBITMQ_CONSUMERS_APPKEY: Final = web.AppKey(
    "APP_RABBITMQ_CONSUMERS_APPKEY", dict[ExchangeName, tuple[QueueName, ConsumerTag]]
)


async def _instrumentation_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = InstrumentationRabbitMessage.model_validate_json(data)
    if rabbit_message.metrics == "service_started":
        service_started(
            app,
            **{key: rabbit_message.model_dump()[key] for key in MONITOR_SERVICE_STARTED_LABELS},
        )
    elif rabbit_message.metrics == "service_stopped":
        service_stopped(
            app,
            **{key: rabbit_message.model_dump()[key] for key in MONITOR_SERVICE_STOPPED_LABELS},
        )
    return True


async def _node_data_updated_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = NodeDataUpdatedEventMessage.model_validate_json(data)
    await apply_node_data_update(
        app,
        user_id=rabbit_message.user_id,
        project_id=rabbit_message.project_id,
        node_id=rabbit_message.node_id,
        changes=rabbit_message.changes,
    )
    return True


_EXCHANGE_TO_PARSER_CONFIG: Final[
    tuple[
        SubscribeArgumentsTuple,
        ...,
    ]
] = (
    SubscribeArgumentsTuple(
        InstrumentationRabbitMessage.get_channel_name(),
        _instrumentation_message_parser,
        {"exclusive_queue": False},
    ),
    SubscribeArgumentsTuple(
        NodeDataUpdatedEventMessage.get_channel_name(),
        _node_data_updated_message_parser,
        {"exclusive_queue": False},
    ),
)


async def _unsubscribe_from_rabbitmq(app) -> None:
    with (
        log_context(_logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"),
        log_catch(_logger, reraise=False),
    ):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await logged_gather(
            *(
                rabbit_client.unsubscribe_consumer(*queue_consumer_map)
                for queue_consumer_map in app[_APP_RABBITMQ_CONSUMERS_APPKEY].values()
            ),
        )


async def on_cleanup_ctx_rabbitmq_consumers(
    app: web.Application,
) -> AsyncIterator[None]:
    app[_APP_RABBITMQ_CONSUMERS_APPKEY] = await subscribe_to_rabbitmq(app, _EXCHANGE_TO_PARSER_CONFIG)
    yield

    # cleanup
    await _unsubscribe_from_rabbitmq(app)
