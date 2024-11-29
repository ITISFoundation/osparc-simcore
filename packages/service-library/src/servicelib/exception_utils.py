import inspect
import logging
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Final, ParamSpec, TypeVar

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


def silence_exceptions(
    exceptions: tuple[type[BaseException], ...]
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
            try:
                return func(*args, **kwargs)
            except exceptions:
                return None

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
            try:
                assert inspect.isawaitable(func)  # nosec
                return await func(*args, **kwargs)
            except exceptions:
                return None

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator
