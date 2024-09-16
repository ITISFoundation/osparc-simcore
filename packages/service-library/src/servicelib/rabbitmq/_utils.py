import logging
import random
import socket
import string
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Final

import aio_pika
from aiormq.exceptions import ChannelPreconditionFailed
from pydantic import NonNegativeInt
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from ..logging_utils import log_context

_logger = logging.getLogger(__file__)


_MINUTE: Final[int] = 60

RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_MS: Final[int] = 15 * _MINUTE * 1000

_PATH_UNIQUE_RABBIT_QUEUE_PREFIX: Final[Path] = (
    Path(gettempdir()) / f"{__name__}_unique_rabbit_queue_prefix"
)
_ALPHABET: Final[str] = string.ascii_letters + string.digits
_CHAR_COUNT: Final[NonNegativeInt] = 6


class RabbitMQRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        logger = logger or _logger

        self.kwargs: dict[str, Any] = {
            "wait": wait_fixed(2),
            "stop": stop_after_delay(3 * _MINUTE),
            "before_sleep": before_sleep_log(logger, logging.WARNING),
            "reraise": True,
        }


async def is_rabbitmq_responsive(url: str) -> bool:
    """True if responsive or raises an error"""
    with log_context(
        _logger, logging.INFO, msg=f"checking RabbitMQ connection at {url=}"
    ):
        async with await aio_pika.connect(url):
            _logger.info("rabbitmq connection established")
        return True


@retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbitmq_responsive(url: str) -> bool:
    """waits for rabbitmq to become responsive"""
    return await is_rabbitmq_responsive(url)


def _get_unique_rabbit_queue_name_prefix() -> str:
    # NOTE: this prefix is guaranteed to be unique for the entire lifecycle of the docker container
    # Why is this desiarable?
    # 1. the code base makes the above assumption, otherwise subcscribers and consumers do not work
    # 2. enables restartability of webserver during [re]deploys
    prefix: str | None = None
    if _PATH_UNIQUE_RABBIT_QUEUE_PREFIX.exists():
        prefix = _PATH_UNIQUE_RABBIT_QUEUE_PREFIX.read_text()

    if prefix is None:
        random_str = "".join(random.choices(_ALPHABET, k=_CHAR_COUNT))  # noqa: S311
        prefix = f"{socket.gethostname()}_{random_str}"
        _PATH_UNIQUE_RABBIT_QUEUE_PREFIX.write_text(prefix)

    return prefix


def get_rabbitmq_client_unique_name(base_name: str) -> str:
    return f"{base_name}_{_get_unique_rabbit_queue_name_prefix()}"


async def declare_queue(
    channel: aio_pika.RobustChannel,
    client_name: str,
    exchange_name: str,
    *,
    exclusive_queue: bool,
    arguments: dict[str, Any] | None = None,
    message_ttl: NonNegativeInt = RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_MS,
) -> aio_pika.abc.AbstractRobustQueue:
    default_arguments = {"x-message-ttl": message_ttl}
    if arguments is not None:
        default_arguments.update(arguments)
    queue_parameters: dict[str, Any] = {
        "durable": True,
        "exclusive": exclusive_queue,
        "arguments": default_arguments,
        # no names for exclusive queues
        #  "name": f"{get_rabbitmq_client_unique_name(client_name)}_{exchange_name}_exclusive",
    }
    if not exclusive_queue:
        # NOTE: setting a name will ensure multiple instance will take their data here
        queue_parameters |= {"name": exchange_name}

    # NOTE: if below line raises something similar to ``ChannelPreconditionFailed: PRECONDITION_FAILED``
    # most likely someone changed the signature of the queues (parameters etc...)
    # Safest way to deal with it:
    #   1. check whether there are any messages for the existing queue in rabbitmq
    #   2. NO messages -> delete queue
    #   3. Found messages:
    #        - save messages
    #        - delete queue
    #        - restore messages
    # Why is this the safest, with an example?
    #   1. a user bought 1000$ of credits
    #   2. for some reason resource usage tracker is unavailable and the messages is stuck in the queue
    #   3. if the queue is deleted, the action relative to this transaction will be lost
    try:
        return await channel.declare_queue(**queue_parameters)
    except ChannelPreconditionFailed:
        _logger.exception(
            "Most likely the rabbit queue parameters have changed. See notes above to fix!"
        )
        raise
