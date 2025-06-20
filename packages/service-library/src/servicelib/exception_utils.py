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


def _should_suppress_exception(
    exc: BaseException,
    predicate: Callable[[BaseException], bool] | None,
    func_name: str,
) -> bool:
    if predicate is None:
        # No predicate provided, suppress all exceptions
        return True

    try:
        return predicate(exc)
    except Exception as predicate_exc:  # pylint: disable=broad-except
        # the predicate function raised an exception
        # log it and do not suppress the original exception
        _logger.warning(
            "Predicate function raised exception %s:%s in %s. "
            "Original exception will be re-raised: %s",
            type(predicate_exc).__name__,
            predicate_exc,
            func_name,
            exc,
        )
        return False


def suppress_exceptions(
    exceptions: tuple[type[BaseException], ...],
    *,
    reason: str,
    predicate: Callable[[BaseException], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to suppress specified exceptions.

    Args:
        exceptions: Tuple of exception types to suppress
        reason: Reason for suppression (for logging)
        predicate: Optional function to check exception attributes.
                  If provided, exception is only suppressed if predicate returns True.

    Example:
        # Suppress all ConnectionError exceptions
        @suppress_exceptions((ConnectionError,), reason="Network issues")
        def my_func(): ...

        # Suppress only ConnectionError with specific errno
        @suppress_exceptions(
            (ConnectionError,),
            reason="Specific network error",
            predicate=lambda e: hasattr(e, 'errno') and e.errno == 104
        )
        def my_func(): ...
    """

    def _decorator(func_or_coro: F) -> F:
        if inspect.iscoroutinefunction(func_or_coro):

            @wraps(func_or_coro)
            async def _async_wrapper(*args, **kwargs) -> Any:
                try:
                    assert inspect.iscoroutinefunction(func_or_coro)  # nosec
                    return await func_or_coro(*args, **kwargs)
                except exceptions as exc:
                    # Check if exception should be suppressed
                    if not _should_suppress_exception(
                        exc, predicate, func_or_coro.__name__
                    ):
                        raise  # Re-raise if predicate returns False or fails

                    _logger.debug(
                        "Caught suppressed exception %s in %s: TIP: %s",
                        exc,
                        func_or_coro.__name__,
                        reason,
                    )
                    return None

            return _async_wrapper  # type: ignore[return-value] # decorators typing is hard

        @wraps(func_or_coro)
        def _sync_wrapper(*args, **kwargs) -> Any:
            try:
                return func_or_coro(*args, **kwargs)
            except exceptions as exc:
                # Check if exception should be suppressed
                if not _should_suppress_exception(
                    exc, predicate, func_or_coro.__name__
                ):
                    raise  # Re-raise if predicate returns False or fails

                _logger.debug(
                    "Caught suppressed exception %s in %s: TIP: %s",
                    exc,
                    func_or_coro.__name__,
                    reason,
                )
                return None

        return _sync_wrapper  # type: ignore[return-value] # decorators typing is hard

    return _decorator
