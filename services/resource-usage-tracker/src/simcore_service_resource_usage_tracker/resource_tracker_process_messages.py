import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingMessages,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
)
from pydantic import parse_raw_as

_logger = logging.getLogger(__name__)


def _parser(x) -> RabbitResourceTrackingMessages:
    return parse_raw_as(RabbitResourceTrackingMessages, x)


async def process_message(
    app: FastAPI, data: bytes  # pylint: disable=unused-argument
) -> bool:
    rabbit_message = _parser(data)
    rabbit_message_type = type(rabbit_message)

    if rabbit_message_type == RabbitResourceTrackingStartedMessage:
        pass
    elif rabbit_message_type == RabbitResourceTrackingHeartbeatMessage:
        pass
    elif rabbit_message_type == RabbitResourceTrackingStoppedMessage:
        pass
    else:
        raise NotImplementedError

    _logger.debug("%s", data)
    return True


async def _process_start():
    pass


async def _process_heartbeat():
    pass


async def _process_stop():
    pass
