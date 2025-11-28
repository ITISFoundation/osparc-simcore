from datetime import timedelta
from typing import Final

from ....generic_scheduler import BaseStepGroup, Operation, SingleStepGroup
from .._common_steps import DoNothing, SetCurrentScheduleId

_WAIT_BEFORE_REPEAT: Final[timedelta] = timedelta(seconds=5)

_steps: list[BaseStepGroup] = [
    SingleStepGroup(
        DoNothing, repeat_steps=True, wait_before_repeat=_WAIT_BEFORE_REPEAT
    ),
]


def get_operation() -> Operation:
    return Operation(
        SingleStepGroup(SetCurrentScheduleId),
        *_steps,
    )
