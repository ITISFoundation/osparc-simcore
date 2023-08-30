import logging
import os
import socket
from collections.abc import Callable
from typing import Any, Final

import aio_pika
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .logging_utils import log_context
from .models import RPCMethodName, RPCNamespace

_logger = logging.getLogger(__file__)


_MINUTE: Final[int] = 60


_RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_S: Final[int] = 15 * _MINUTE


class RabbitMQRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        logger = logger or _logger

        self.kwargs = {
            "wait": wait_fixed(2),
            "stop": stop_after_delay(3 * _MINUTE),
            "before_sleep": before_sleep_log(logger, logging.WARNING),
            "reraise": True,
        }


@retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbitmq_responsive(url: str) -> bool:
    """Check if something responds to ``url``"""
    with log_context(
        _logger, logging.INFO, msg=f"checking RabbitMQ connection at {url=}"
    ):
        async with await aio_pika.connect(url):
            _logger.info("rabbitmq connection established")
        return True


async def rpc_register_entries(
    rabbit_client,
    entries: dict[str, str],
    handler: Callable[..., Any],
) -> None:
    """
    Bind a local `handler` to a `namespace` derived from the provided `entries`
    dictionary.

    NOTE: This is a helper enforce the pattern defined in `rpc_register`'s
    docstring.
    """
    await rabbit_client.rpc_register_handler(
        RPCNamespace.from_entries(entries),
        method_name=RPCMethodName(handler.__name__),
        handler=handler,
    )


def get_rabbitmq_client_unique_name(base_name: str) -> str:
    return f"{base_name}_{socket.gethostname()}_{os.getpid()}"


async def declare_queue(
    channel: aio_pika.RobustChannel,
    client_name: str,
    exchange_name: str,
    *,
    exclusive_queue: bool,
) -> aio_pika.abc.AbstractRobustQueue:
    queue_parameters = {
        "durable": True,
        "exclusive": exclusive_queue,
        "arguments": {"x-message-ttl": _RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_S},
        "name": f"{get_rabbitmq_client_unique_name(client_name)}_{exchange_name}_exclusive",
    }
    if not exclusive_queue:
        # NOTE: setting a name will ensure multiple instance will take their data here
        queue_parameters |= {"name": exchange_name}
    return await channel.declare_queue(**queue_parameters)
