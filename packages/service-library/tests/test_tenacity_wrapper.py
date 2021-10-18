# pylint: disable=redefined-outer-name

import logging
from collections import namedtuple
from typing import Type

import pytest
from servicelib.tenacity_wrapper import add_defaults
from tenacity import AsyncRetrying, RetryError, Retrying, retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


TestParams = namedtuple(
    "TestParams", "expected_error, reraise, overwrite_retry_paramenter"
)


# UTILS


class CustomTestException(Exception):
    pass


def _print_and_raise() -> None:
    print(">>>>> my code runs here")
    raise CustomTestException("expected error")


# FIXTURES


@pytest.fixture
def max_retires() -> int:
    return 3


@pytest.fixture
def wait_interval() -> float:
    return 0.01


# TESTS


@pytest.mark.parametrize(
    "expected_error, reraise, overwrite_retry_paramenter",
    [
        TestParams(
            expected_error=CustomTestException,
            reraise=True,
            overwrite_retry_paramenter=True,
        ),
        TestParams(
            expected_error=RetryError,
            reraise=False,
            overwrite_retry_paramenter=True,
        ),
    ],
)
async def test_async_retrying(
    expected_error: Type[Exception],
    reraise: bool,
    overwrite_retry_paramenter: bool,
    max_retires: int,
    wait_interval: float,
) -> None:
    counter = 0

    with pytest.raises(expected_error):
        async for attempt in AsyncRetrying(
            **add_defaults(
                overwrite_retry_paramenter=overwrite_retry_paramenter,
                stop=stop_after_attempt(max_retires),
                wait=wait_fixed(wait_interval),
                reraise=reraise,
            )
        ):
            with attempt:
                counter += 1
                _print_and_raise()

    assert counter == max_retires


def test_retrying(max_retires: int, wait_interval: float) -> None:
    counter = 0

    with pytest.raises(CustomTestException):
        for attempt in Retrying(
            **add_defaults(
                stop=stop_after_attempt(max_retires), wait=wait_fixed(wait_interval)
            )
        ):
            with attempt:
                counter += 1
                _print_and_raise()

    assert counter == max_retires


def test_try_decorator_callable(max_retires: int, wait_interval: float) -> None:
    # variables normally passed by reference are not accessible
    # in nested function's scope
    counter = [0]

    @retry(
        **add_defaults(
            stop=stop_after_attempt(max_retires), wait=wait_fixed(wait_interval)
        )
    )
    def failing_callable() -> None:
        counter[0] += 1
        _print_and_raise()

    with pytest.raises(CustomTestException):
        failing_callable()

    assert counter[0] == max_retires


async def test_try_decorator_coroutine(max_retires: int, wait_interval: float) -> None:
    # variables normally passed by reference are not accessible
    # in nested function's scope
    counter = [0]

    @retry(
        **add_defaults(
            stop=stop_after_attempt(max_retires), wait=wait_fixed(wait_interval)
        )
    )
    async def failing_coroutine() -> None:
        counter[0] += 1
        _print_and_raise()

    with pytest.raises(CustomTestException):
        await failing_coroutine()

    assert counter[0] == max_retires


async def test_no_fail_after_first_time(max_retires: int, wait_interval: float) -> None:
    # variables normally passed by reference are not accessible
    # in nested function's scope
    counter = [0]

    @retry(
        **add_defaults(
            stop=stop_after_attempt(max_retires), wait=wait_fixed(wait_interval)
        )
    )
    async def failing_coroutine() -> None:
        counter[0] += 1

        logger.debug("[try=%s] before code", counter[0])
        if counter[0] == 1:
            logger.debug("[try=%s] will raise error", counter[0])
            raise CustomTestException("expected error")
        logger.debug("[try=%s] after code", counter[0])

    await failing_coroutine()

    assert counter[0] == 2
