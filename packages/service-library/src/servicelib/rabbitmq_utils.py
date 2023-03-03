# FIXME: move to settings-library or refactor

import logging
import re
from typing import Final, Optional

import aio_pika
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .logging_utils import log_context
from .rabbitmq_errors import RPCNamespaceInvalidCharsError, RPCNamespaceTooLongError

log = logging.getLogger(__file__)


_MINUTE: Final[int] = 60
_NAMESPACE_CHAR_LIMIT: Final[int] = 100

REGEX_VALIDATE_RABBIT_QUEUE_NAME: Final[str] = r"^[\w\-\.]{1,255}$"

RPCNamespace = str


def get_namespace(entries: dict[str, str]) -> RPCNamespace:
    """
    Given a list of entries creates a namespace to be used in declaring the rabbitmq queue.
    Keeping this to a predefined length
    """

    namespace = "-".join(f"{k}_{v}" for k, v in sorted(entries.items()))
    if len(namespace) > _NAMESPACE_CHAR_LIMIT:
        raise RPCNamespaceTooLongError(
            namespace=namespace,
            namespace_length=len(namespace),
            char_limit=_NAMESPACE_CHAR_LIMIT,
        )

    if not re.compile(REGEX_VALIDATE_RABBIT_QUEUE_NAME).match(namespace):
        raise RPCNamespaceInvalidCharsError(
            namespace=namespace, match_regex=REGEX_VALIDATE_RABBIT_QUEUE_NAME
        )
    return namespace


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
