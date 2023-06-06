import asyncio
import logging
import os
import re
import socket
from typing import Any, Callable, Final, Pattern

import aio_pika
import aiormq
from pydantic import ConstrainedStr, parse_obj_as
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .logging_utils import log_context

_logger = logging.getLogger(__file__)


_MINUTE: Final[int] = 60

REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS: Final[str] = r"^[\w\-\.]*$"
_RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_S: Final[int] = 15 * _MINUTE


class RPCMethodName(ConstrainedStr):
    min_length: int = 1
    max_length: int = 252
    regex: Pattern[str] | None = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)


class RPCNamespace(ConstrainedStr):
    min_length: int = 1
    max_length: int = 252
    regex: Pattern[str] | None = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)

    @classmethod
    def from_entries(cls, entries: dict[str, str]) -> "RPCNamespace":
        """
        Given a list of entries creates a namespace to be used in declaring the rabbitmq queue.
        Keeping this to a predefined length
        """
        composed_string = "-".join(f"{k}_{v}" for k, v in sorted(entries.items()))
        return parse_obj_as(cls, composed_string)


class RPCNamespacedMethodName(ConstrainedStr):
    min_length: int = 1
    max_length: int = 255
    regex: Pattern[str] | None = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)

    @classmethod
    def from_namespace_and_method(
        cls, namespace: RPCNamespace, method_name: RPCMethodName
    ) -> "RPCNamespacedMethodName":
        namespaced_method_name = f"{namespace}.{method_name}"
        return parse_obj_as(cls, namespaced_method_name)


class RabbitMQRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    def __init__(self, logger: logging.Logger | None = None):
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
        connection = await aio_pika.connect(url)
        await connection.close()
        _logger.info("rabbitmq connection established")
        return True


async def rpc_register_entries(
    rabbit_client: "RabbitMQClient",
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
        method_name=handler.__name__,
        handler=handler,
    )


def connection_close_callback(
    sender: Any,  # pylint: disable=unused-argument
    exc: BaseException | None,
) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            _logger.info("Rabbit connection cancelled")
        elif isinstance(exc, aiormq.exceptions.ConnectionClosed):
            _logger.info("Rabbit connection closed: %s", exc)
        else:
            _logger.error(
                "Rabbit connection closed with exception from %s",
                exc,
            )


def get_rabbitmq_client_unique_name(base_name: str) -> str:
    return f"{base_name}_{socket.gethostname()}_{os.getpid()}"


def channel_close_callback(
    client: "RabbitMQClient",
    sender: Any,  # pylint: disable=unused-argument
    exc: BaseException | None,
) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            _logger.info("Rabbit channel cancelled")
        elif isinstance(exc, aiormq.exceptions.ChannelNotFoundEntity):
            _logger.error("The RabbitMQ client is in a bad state! %s", exc)
            client._bad_state = True  # pylint: disable=protected-access
            # ideally we need to re-init. close the client and re-init it completely.
        elif isinstance(exc, aiormq.exceptions.ChannelClosed):
            _logger.info("Rabbit channel closed")
        else:
            _logger.error(
                "Rabbit channel closed with exception from %s",
                exc,
            )


async def get_connection(
    rabbit_broker: str, connection_name: str
) -> aio_pika.abc.AbstractRobustConnection:
    # NOTE: to show the connection name in the rabbitMQ UI see there
    # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
    #
    url = f"{rabbit_broker}?name={get_rabbitmq_client_unique_name(connection_name)}&heartbeat=5"
    connection = await aio_pika.connect_robust(
        url,
        client_properties={"connection_name": connection_name},
    )
    connection.close_callbacks.add(connection_close_callback)
    return connection


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
    queue = await channel.declare_queue(**queue_parameters)
    return queue
