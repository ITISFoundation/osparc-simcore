from math import ceil
from time import sleep
from typing import Final

import pytest
from pydantic import PositiveFloat, PositiveInt
from servicelib.exception_utils import DelayedExceptionHandler, suppress_exceptions

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
    def __init__(self, code: int = 0, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(message)


class AnotherCustomError(Exception):
    pass


@suppress_exceptions((CustomError,), reason="CustomError is silenced")
def sync_function(*, raise_error: bool, raise_another_error: bool) -> str:
    if raise_error:
        raise CustomError
    if raise_another_error:
        raise AnotherCustomError
    return "Success"


@suppress_exceptions((CustomError,), reason="CustomError is silenced")
async def async_function(*, raise_error: bool, raise_another_error: bool) -> str:
    if raise_error:
        raise CustomError
    if raise_another_error:
        raise AnotherCustomError
    return "Success"


# Test functions with predicate
@suppress_exceptions(
    (CustomError,),
    reason="Only suppress CustomError with code >= 100",
    predicate=lambda e: hasattr(e, "code") and e.code >= 100,
)
def sync_function_with_predicate(error_code: int = 0) -> str:
    if error_code > 0:
        raise CustomError(code=error_code, message=f"Error {error_code}")
    return "Success"


@suppress_exceptions(
    (CustomError,),
    reason="Only suppress CustomError with code >= 100",
    predicate=lambda e: hasattr(e, "code") and e.code >= 100,
)
async def async_function_with_predicate(error_code: int = 0) -> str:
    if error_code > 0:
        raise CustomError(code=error_code, message=f"Error {error_code}")
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


def test_sync_function_predicate_suppresses_matching_exception():
    result = sync_function_with_predicate(
        error_code=150
    )  # code >= 100, should be suppressed
    assert result is None


def test_sync_function_predicate_raises_non_matching_exception():
    with pytest.raises(CustomError):
        sync_function_with_predicate(error_code=50)  # code < 100, should be raised


def test_sync_function_predicate_no_exception():
    result = sync_function_with_predicate(error_code=0)
    assert result == "Success"


async def test_async_function_predicate_suppresses_matching_exception():
    result = await async_function_with_predicate(
        error_code=200
    )  # code >= 100, should be suppressed
    assert result is None


async def test_async_function_predicate_raises_non_matching_exception():
    with pytest.raises(CustomError):
        await async_function_with_predicate(
            error_code=25
        )  # code < 100, should be raised


async def test_async_function_predicate_no_exception():
    result = await async_function_with_predicate(error_code=0)
    assert result == "Success"


@suppress_exceptions(
    (ValueError, TypeError),
    reason="Complex predicate test",
    predicate=lambda e: "suppress" in str(e).lower(),
)
def function_with_complex_predicate(message: str) -> str:
    if "value" in message:
        raise ValueError(message)
    if "type" in message:
        raise TypeError(message)
    return "Success"


def test_complex_predicate_suppresses_matching():
    result = function_with_complex_predicate("please suppress this value error")
    assert result is None


def test_complex_predicate_raises_non_matching():
    with pytest.raises(ValueError, match="value error without keyword"):
        function_with_complex_predicate("value error without keyword")


def test_complex_predicate_different_exception_type():
    result = function_with_complex_predicate("type error with suppress keyword")
    assert result is None


# Test predicate exception handling
@suppress_exceptions(
    (ValueError,),
    reason="Predicate that raises exception",
    predicate=lambda _: bool(1 / 0),  # This will raise ZeroDivisionError
)
def function_with_failing_predicate() -> str:
    msg = "Original error"
    raise ValueError(msg)


@suppress_exceptions(
    (ValueError,),
    reason="Predicate that raises exception",
    predicate=lambda _: bool(1 / 0),  # This will raise ZeroDivisionError
)
async def async_function_with_failing_predicate() -> str:
    msg = "Original error"
    raise ValueError(msg)


def test_sync_function_predicate_exception_reraised(caplog):
    with pytest.raises(ValueError, match="Original error"):
        function_with_failing_predicate()

    # Check that warning was logged
    assert "Predicate function raised exception" in caplog.text
    assert "ZeroDivisionError" in caplog.text


async def test_async_function_predicate_exception_reraised(caplog):
    with pytest.raises(ValueError, match="Original error"):
        await async_function_with_failing_predicate()

    # Check that warning was logged
    assert "Predicate function raised exception" in caplog.text
    assert "ZeroDivisionError" in caplog.text


@suppress_exceptions(
    (ValueError,),
    reason="Predicate that accesses invalid attribute",
    predicate=lambda e: e.nonexistent_attribute == "test",
)
def function_with_attribute_error_predicate() -> str:
    msg = "Original error"
    raise ValueError(msg)


def test_predicate_attribute_error_reraised(caplog):
    with pytest.raises(ValueError, match="Original error"):
        function_with_attribute_error_predicate()

    # Check that warning was logged about predicate failure
    assert "Predicate function raised exception" in caplog.text
    assert "AttributeError" in caplog.text


@suppress_exceptions(
    (ValueError,),
    reason="Predicate that sometimes works",
    predicate=lambda e: len(str(e)) > 5,  # Safe predicate
)
def function_with_working_predicate(message: str) -> str:
    raise ValueError(message)


def test_predicate_works_normally():
    # Short message - predicate returns False, exception re-raised
    with pytest.raises(ValueError):
        function_with_working_predicate("Hi")

    # Long message - predicate returns True, exception suppressed
    result = function_with_working_predicate("This is a long error message")
    assert result is None
