# FIXME: move to settings-library or refactor

import logging
from typing import Final, Optional

import aio_pika
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

from .logging_utils import log_context

log = logging.getLogger(__file__)


_MINUTE: Final[int] = 60


class RabbitMQRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        logger = logger or log

        self.kwargs = dict(
            wait=wait_fixed(2),
            stop=stop_after_delay(3 * _MINUTE),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )


@retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbitmq_responsive(url: str) -> bool:
    """Check if something responds to ``url``"""
    with log_context(log, logging.INFO, msg=f"checking RabbitMQ connection at {url=}"):
        connection = await aio_pika.connect(url)
        await connection.close()
        return True
