""" Common retry policies to access services

    Other than tenacity, this module SHOULD NOT have other dependencies
"""

import logging

from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

log = logging.getLogger(__name__)


class PostgresRetryPolicyUponInitialization:
    """Retry policy upon service initialization"""

    WAIT_SECS = 5
    ATTEMPTS_COUNT = 20

    def __init__(self, logger: logging.Logger | None = None):
        logger = logger or log

        self.kwargs = {
            "wait": wait_fixed(self.WAIT_SECS),
            "stop": stop_after_attempt(self.ATTEMPTS_COUNT),
            "before_sleep": before_sleep_log(logger, logging.WARNING),
            "reraise": True,
        }


class RedisRetryPolicyUponInitialization(PostgresRetryPolicyUponInitialization):
    ...
