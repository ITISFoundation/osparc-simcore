from math import ceil
from time import sleep
from typing import Final

import pytest
from pydantic import PositiveFloat, PositiveInt
from servicelib.exception_utils import DelayedExceptionHandler

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
            delayed_handler_external_service.except_delay_raise(e)
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
