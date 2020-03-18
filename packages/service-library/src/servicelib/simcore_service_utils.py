import logging
from typing import Optional

from tenacity import before_sleep_log, stop_after_attempt, wait_fixed

log = logging.getLogger(__name__)


class SimcoreRetryPolicyUponInitialization:
    """ Retry policy upon service initialization
    """

    WAIT_SECS = 5
    ATTEMPTS_COUNT = 12

    def __init__(self, logger: Optional[logging.Logger] = None):
        logger = logger or log

        self.kwargs = dict(
            wait=wait_fixed(self.WAIT_SECS),
            stop=stop_after_attempt(self.ATTEMPTS_COUNT),
            before_sleep=before_sleep_log(logger, logging.INFO),
            reraise=True,
        )
