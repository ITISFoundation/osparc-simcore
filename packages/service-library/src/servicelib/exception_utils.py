import inspect
import logging
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any, Final, ParamSpec, TypeVar

from pydantic import BaseModel, Field, NonNegativeFloat, PrivateAttr

_logger = logging.getLogger(__name__)

_SKIPS_MESSAGE: Final[str] = "skip(s) of exception"


class DelayedExceptionHandler(BaseModel):
    """
    Allows to ignore an exception for an established
    period of time after which it is raised.

    This use case most commonly occurs when dealing with
    external systems.
    For example, due to poor network  performance or
    network congestion, an external system which is healthy,
    currently is not reachable any longer.
    A possible solution:
    - ignore exceptions for an interval in which the
        system usually is reachable again by not
        raising the error
    - if the error persist give up and raise it

    Example code usage:

        delayed_handler_external_service = DelayedExceptionHandler(
            delay_for=60
        )
        try:
            function_called_periodically_accessing_external_service()
        except TargetException as e:
            delayed_handler_external_service.try_to_raise(e)
        else:
            delayed_handler_external_service.else_reset()
    """

    _first_exception_skip: datetime | None = PrivateAttr(None)
    _failure_counter: int = PrivateAttr(0)

    delay_for: NonNegativeFloat = Field(
        description="interval of time during which exceptions are ignored"
    )

    def try_to_raise(self, exception: BaseException) -> None:
        """raises `exception` after `delay_for` passed from the first call"""
        self._failure_counter += 1

        # first time the exception was detected
        if self._first_exception_skip is None:
            self._first_exception_skip = datetime.utcnow()

        # raise if subsequent exception is outside of delay window
        elif (
            datetime.utcnow() - self._first_exception_skip
        ).total_seconds() > self.delay_for:
            raise exception

        _logger.debug("%s %s: %s", self._failure_counter, _SKIPS_MESSAGE, exception)

    def else_reset(self) -> None:
        """error no longer occurs reset tracking"""
        self._first_exception_skip = None
        self._failure_counter = 0


P = ParamSpec("P")
R = TypeVar("R")

F = TypeVar("F", bound=Callable[..., Any])


def silence_exceptions(exceptions: tuple[type[BaseException], ...]) -> Callable[[F], F]:
    def _decorator(func_or_coro: F) -> F:

        if inspect.iscoroutinefunction(func_or_coro):

            @wraps(func_or_coro)
            async def _async_wrapper(*args, **kwargs) -> Any:
                try:
                    assert inspect.iscoroutinefunction(func_or_coro)  # nosec
                    return await func_or_coro(*args, **kwargs)
                except exceptions:
                    return None

            return _async_wrapper  # type: ignore[return-value] # decorators typing is hard

        @wraps(func_or_coro)
        def _sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func_or_coro(*args, **kwargs)
            except exceptions:
                return None

        return _sync_wrapper  # type: ignore[return-value] # decorators typing is hard

    return _decorator
