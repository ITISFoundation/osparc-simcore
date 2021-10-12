# pylint: disable=redefined-outer-name

import pytest
from servicelib.tenacity_wrapper import AsyncRetrying, Retrying, retry
from tenacity import RetryError
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


class CustomTestException(Exception):
    pass


def _print_and_raise() -> None:
    print(">>>>> my code runs here")
    raise CustomTestException("expected error")


@pytest.fixture
def max_retires() -> int:
    return 3


@pytest.fixture
def wait_interval() -> float:
    return 0.01


async def test_async_retrying(max_retires: int, wait_interval: float) -> None:
    counter = 0

    with pytest.raises(RetryError):
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_retires),
            wait=wait_fixed(wait_interval),
        ):
            with attempt:
                counter += 1
                _print_and_raise()

    assert counter == max_retires


def test_retrying(max_retires: int, wait_interval: float) -> None:
    counter = 0

    with pytest.raises(RetryError):
        for attempt in Retrying(
            stop=stop_after_attempt(max_retires),
            wait=wait_fixed(wait_interval),
        ):
            with attempt:
                counter += 1
                _print_and_raise()

    assert counter == max_retires


def test_try_decorator_callable(max_retires: int, wait_interval: float) -> None:
    # variables normally passed by reference are not accessible
    # in nested function's scope
    counter = [0]

    @retry(stop=stop_after_attempt(max_retires), wait=wait_fixed(wait_interval))
    def failing_callable() -> None:
        counter[0] += 1
        _print_and_raise()

    with pytest.raises(RetryError):
        failing_callable()

    assert counter[0] == max_retires


async def test_try_decorator_coroutine(max_retires: int, wait_interval: float) -> None:
    # variables normally passed by reference are not accessible
    # in nested function's scope
    counter = [0]

    @retry(stop=stop_after_attempt(max_retires), wait=wait_fixed(wait_interval))
    async def failing_coroutine() -> None:
        counter[0] += 1
        _print_and_raise()

    with pytest.raises(RetryError):
        await failing_coroutine()

    assert counter[0] == max_retires
