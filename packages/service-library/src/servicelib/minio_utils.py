import logging

from tenacity import before_sleep_log, stop_after_attempt, wait_fixed

log = logging.getLogger(__name__)


class ServiceRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    WAIT_SECS = 2
    ATTEMPTS_COUNT = 40

    def __init__(self, logger: logging.Logger | None = None):
        logger = logger or log

        self.kwargs = dict(
            wait=wait_fixed(self.WAIT_SECS),
            stop=stop_after_attempt(self.ATTEMPTS_COUNT),
            before_sleep=before_sleep_log(logger, logging.INFO),
            reraise=True,
        )
