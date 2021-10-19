# pylint: disable=redefined-outer-name

import logging
from collections import namedtuple
from dataclasses import dataclass
from typing import Callable, Coroutine, List, Type

import pytest
from servicelib.tenacity_wrapper import add_defaults
from tenacity import RetryError, Retrying, retry
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


@dataclass
class TestContext:
    counter: int = 0


TestCase = namedtuple("TestCase", "expected_error, reraise, overwrite_retry_paramenter")


# UTILS


class CustomTestException(Exception):
    pass


def _test_code(test_context: TestContext) -> None:
    test_context.counter += 1

    logger.debug("[try=%s] before code", test_context.counter)
    if test_context.counter == 1:
        logger.debug("[try=%s] will raise error", test_context.counter)
        raise CustomTestException("expected error")
    logger.debug("[try=%s] after code", test_context.counter)


# FIXTURES


@pytest.fixture
def max_retires() -> int:
    return 3


@pytest.fixture
def wait_interval() -> float:
    return 0.01


@pytest.fixture
def test_context() -> TestContext:
    return TestContext()


@pytest.fixture
def failing_callable_factory(wait_interval: float) -> Callable:
    def assemble(test_context: TestContext, max_retires: int) -> Callable:
        @retry(
            **add_defaults(
                stop=stop_after_attempt(max_retires),
                wait=wait_fixed(wait_interval),
                reraise=True,
                overwrite_retry_paramenter=True,
            )
        )
        def failing_callable() -> None:
            _test_code(test_context)

        return failing_callable

    return assemble


@pytest.fixture
def failing_coroutine_factory(wait_interval: float) -> Callable:
    def assemble(test_context: TestContext, max_retires: int) -> Coroutine:
        @retry(
            **add_defaults(
                stop=stop_after_attempt(max_retires),
                wait=wait_fixed(wait_interval),
                reraise=True,
                overwrite_retry_paramenter=True,
            )
        )
        async def failing_coroutine() -> None:
            _test_code(test_context)

        return failing_coroutine

    return assemble


def get_test_cases() -> List[TestCase]:
    return [
        TestCase(
            expected_error=CustomTestException,
            reraise=True,
            overwrite_retry_paramenter=True,
        ),
        TestCase(
            expected_error=RetryError,
            reraise=False,
            overwrite_retry_paramenter=True,
        ),
    ]


# TESTS


@pytest.mark.parametrize(
    "expected_error, reraise, overwrite_retry_paramenter",
    get_test_cases(),
)
async def test_async_retrying(
    expected_error: Type[Exception],
    reraise: bool,
    overwrite_retry_paramenter: bool,
    wait_interval: float,
    test_context: TestContext,
) -> None:
    with pytest.raises(expected_error):
        async for attempt in AsyncRetrying(
            **add_defaults(
                overwrite_retry_paramenter=overwrite_retry_paramenter,
                stop=stop_after_attempt(1),
                wait=wait_fixed(wait_interval),
                reraise=reraise,
            )
        ):
            with attempt:
                _test_code(test_context)

    assert test_context.counter == 1


@pytest.mark.parametrize(
    "expected_error, reraise, overwrite_retry_paramenter",
    get_test_cases(),
)
def test_retrying(
    expected_error: Type[Exception],
    reraise: bool,
    overwrite_retry_paramenter: bool,
    wait_interval: float,
    test_context: TestContext,
) -> None:
    with pytest.raises(expected_error):
        for attempt in Retrying(
            **add_defaults(
                stop=stop_after_attempt(1),
                wait=wait_fixed(wait_interval),
                reraise=reraise,
                overwrite_retry_paramenter=overwrite_retry_paramenter,
            )
        ):
            with attempt:
                _test_code(test_context)

    assert test_context.counter == 1


def test_try_decorator_callable(
    failing_callable_factory: Callable, max_retires: int, test_context: TestContext
) -> None:
    failing_callable = failing_callable_factory(test_context, max_retires)

    failing_callable()
    assert test_context.counter == max_retires - 1


def test_try_decorator_callable_failing(
    failing_callable_factory: Callable, test_context: TestContext
) -> None:
    failing_callable = failing_callable_factory(test_context, 1)

    with pytest.raises(CustomTestException):
        failing_callable()
    assert test_context.counter == 1


async def test_try_decorator_coroutine(
    failing_coroutine_factory: Callable, test_context: TestContext
) -> None:

    failing_coroutine = failing_coroutine_factory(test_context, 1)

    with pytest.raises(CustomTestException):
        await failing_coroutine()
    assert test_context.counter == 1


async def test_no_fail_after_first_time(
    failing_coroutine_factory: Callable, max_retires: int, test_context: TestContext
) -> None:
    failing_coroutine = failing_coroutine_factory(test_context, max_retires)

    await failing_coroutine()
    assert test_context.counter == max_retires - 1
