import logging
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Final

from common_library.errors_classes import OsparcErrorMixin
from tenacity import AsyncRetrying, RetryCallState, TryAgain
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_logger = logging.getLogger(__name__)


_DEFAULT_CHECK_INTERVAL: Final[timedelta] = timedelta(seconds=1)
_DEFAULT_TIMEOUT_INTERVAL: Final[timedelta] = timedelta(seconds=30)


class CouldNotReachServiceError(OsparcErrorMixin, Exception):
    msg_template: str = "Could not contact service '{service_name}' at '{endpoint}'. Look above for details."


def _before_sleep_log(
    logger: logging.Logger, service_name: str, endpoint: str
) -> Callable[[RetryCallState], None]:
    def log_it(retry_state: RetryCallState) -> None:
        assert retry_state  # nosec
        assert retry_state.next_action  # nosec

        logger.warning(
            "Retrying (attempt %s) to contact '%s' at '%s' in %s seconds.",
            retry_state.attempt_number,
            service_name,
            endpoint,
            retry_state.next_action.sleep,
        )

    return log_it


async def _attempt_to_wait_for_handler(
    async_handler: Callable[..., Awaitable],
    *args,
    service_name: str,
    endpoint: str,
    check_interval: timedelta,
    timeout: timedelta,
    **kwargs,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(check_interval),
        stop=stop_after_delay(timeout.total_seconds()),
        before_sleep=_before_sleep_log(_logger, service_name, endpoint),
        reraise=True,
    ):
        with attempt:
            if await async_handler(*args, **kwargs) is False:
                raise TryAgain


async def wait_for_service_liveness(
    async_handler: Callable[..., Awaitable],
    *args,
    service_name: str,
    endpoint: str,
    check_interval: timedelta | None = None,
    timeout: timedelta | None = None,
    **kwargs,
) -> None:
    """waits for async_handler to return ``True`` or ``None`` instead of
    raising errors or returning ``False``

    Arguments:
        async_handler -- handler to execute
        service_name -- service reference for whom investigates the logs
        endpoint -- endpoint address for whom investigates the logs (only used for logging)

    Keyword Arguments:
        check_interval -- interval at which service check is ran (default: {_DEFAULT_CHECK_INTERVAL})
        timeout -- stops trying to contact service and raises ``CouldNotReachServiceError``
            (default: {_DEFAULT_TIMEOUT_INTERVAL})

    Raises:
        CouldNotReachServiceError: if it was not able to contact the service in time
    """

    if check_interval is None:
        check_interval = _DEFAULT_CHECK_INTERVAL
    if timeout is None:
        timeout = _DEFAULT_TIMEOUT_INTERVAL

    try:
        start = time.time()
        await _attempt_to_wait_for_handler(
            async_handler,
            *args,
            service_name=service_name,
            endpoint=endpoint,
            check_interval=check_interval,
            timeout=timeout,
            **kwargs,
        )
        elapsed_ms = (time.time() - start) * 1000
        _logger.info(
            "Service '%s' found at '%s' after %.2f ms",
            service_name,
            endpoint,
            elapsed_ms,
        )
    except Exception as e:
        raise CouldNotReachServiceError(
            service_name=service_name, endpoint=endpoint
        ) from e
