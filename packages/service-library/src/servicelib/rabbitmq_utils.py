# FIXME: move to settings-library or refactor

import logging
from typing import Final, Optional

from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

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
