from math import ceil
from time import sleep
from typing import Final

import pytest
from pydantic import PositiveFloat, PositiveInt
from servicelib.exception_utils import DelayedExceptionHandler, silence_exceptions

TOLERANCE: Final[PositiveFloat] = 0.1
SLEEP_FOR: Final[PositiveFloat] = TOLERANCE * 0.1
ITERATIONS: Final[PositiveInt] = int(ceil(TOLERANCE / SLEEP_FOR)) + 1


class TargetException(Exception):
    pass


def workflow(*, stop_raising_after: PositiveInt) -> int:
    counter = 0

    def function_which_can_raise():
        nonlocal counter
        counter += 1

        if counter < stop_raising_after:
            raise TargetException()

    delayed_handler_external_service = DelayedExceptionHandler(delay_for=TOLERANCE)

    def periodic_event():
        try:
            function_which_can_raise()
        except TargetException as e:
            delayed_handler_external_service.try_to_raise(e)
        else:
            delayed_handler_external_service.else_reset()

    for _ in range(ITERATIONS):
        periodic_event()
        sleep(SLEEP_FOR)

    return counter


def test_workflow_passes() -> None:
    assert workflow(stop_raising_after=2) == ITERATIONS


def test_workflow_raises() -> None:
    with pytest.raises(TargetException):
        workflow(stop_raising_after=ITERATIONS + 1)


# Define some custom exceptions for testing
class CustomError(Exception):
    pass


class AnotherCustomError(Exception):
    pass


@silence_exceptions((CustomError,))
def sync_function(*, raise_error: bool, raise_another_error: bool) -> str:
    if raise_error:
        raise CustomError
    if raise_another_error:
        raise AnotherCustomError
    return "Success"


@silence_exceptions((CustomError,))
async def async_function(*, raise_error: bool, raise_another_error: bool) -> str:
    if raise_error:
        raise CustomError
    if raise_another_error:
        raise AnotherCustomError
    return "Success"


def test_sync_function_no_exception():
    result = sync_function(raise_error=False, raise_another_error=False)
    assert result == "Success"


def test_sync_function_with_exception_is_silenced():
    result = sync_function(raise_error=True, raise_another_error=False)
    assert result is None


async def test_async_function_no_exception():
    result = await async_function(raise_error=False, raise_another_error=False)
    assert result == "Success"


async def test_async_function_with_exception_is_silenced():
    result = await async_function(raise_error=True, raise_another_error=False)
    assert result is None


def test_sync_function_with_different_exception():
    with pytest.raises(AnotherCustomError):
        sync_function(raise_error=False, raise_another_error=True)


async def test_async_function_with_different_exception():
    with pytest.raises(AnotherCustomError):
        await async_function(raise_error=False, raise_another_error=True)
