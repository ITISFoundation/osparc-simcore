import logging
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, NonNegativeFloat, PrivateAttr

log = logging.getLogger(__name__)


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

    _first_exception_skip: Optional[datetime] = PrivateAttr(None)
    _failure_counter: int = PrivateAttr(0)

    delay_for: NonNegativeFloat = Field(
        description="interval of time during which exceptions are ignored"
    )

    def try_to_raise(self, exception: BaseException) -> None:
        """raises `exception` after `delay_for` passed from the first call"""
        self._failure_counter += 1

        # first time the exception was detected
        if self._first_exception_skip is None:
            self._first_exception_skip = datetime.now(timezone.utc).replace(tzinfo=None)

        # raise if subsequent exception is outside of delay window
        elif (
            datetime.now(timezone.utc).replace(tzinfo=None) - self._first_exception_skip
        ).total_seconds() > self.delay_for:
            raise exception

        # ignore if exception inside delay window
        log.warning("%s skip(s) of exception: %s", self._failure_counter, exception)

    def else_reset(self) -> None:
        """error no longer occurs reset tracking"""
        self._first_exception_skip = None
        self._failure_counter = 0
