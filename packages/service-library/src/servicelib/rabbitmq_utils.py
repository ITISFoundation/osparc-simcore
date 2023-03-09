# FIXME: move to settings-library or refactor

import logging
import re
from typing import Awaitable, Final, Optional, Pattern

import aio_pika
from pydantic import ConstrainedStr, parse_obj_as
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .logging_utils import log_context

log = logging.getLogger(__file__)


_MINUTE: Final[int] = 60

REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS: Final[str] = r"^[\w\-\.]*$"


class RPCMethodName(ConstrainedStr):
    min_length: int = 1
    max_length: int = 252
    regex: Optional[Pattern[str]] = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)


class RPCNamespace(ConstrainedStr):
    min_length: int = 1
    max_length: int = 252
    regex: Optional[Pattern[str]] = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)

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
    regex: Optional[Pattern[str]] = re.compile(REGEX_RABBIT_QUEUE_ALLOWED_SYMBOLS)

    @classmethod
    def from_namespace_and_method(
        cls, namespace: RPCNamespace, method_name: RPCMethodName
    ) -> "RPCNamespacedMethodName":
        namespaced_method_name = f"{namespace}.{method_name}"
        return parse_obj_as(cls, namespaced_method_name)


class RabbitMQRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        logger = logger or log

        self.kwargs = {
            "wait": wait_fixed(2),
            "stop": stop_after_delay(3 * _MINUTE),
            "before_sleep": before_sleep_log(logger, logging.WARNING),
            "reraise": True,
        }


@retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbitmq_responsive(url: str) -> bool:
    """Check if something responds to ``url``"""
    with log_context(log, logging.INFO, msg=f"checking RabbitMQ connection at {url=}"):
        connection = await aio_pika.connect(url)
        await connection.close()
        log.info("rabbitmq connection established")
        return True


async def rpc_register_entries(
    rabbit_client: "RabbitMQClient", entries: dict[str, str], handler: Awaitable
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
