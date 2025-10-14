from datetime import timedelta
from typing import Final

from ....generic_scheduler import Operation, SingleStepGroup
from .._common_steps import DoNothing, RegisterScheduleId, UnRegisterScheduleId

_WAIT_BEFORE_REPEAT: Final[timedelta] = timedelta(seconds=5)

operation = Operation(
    SingleStepGroup(RegisterScheduleId),
    SingleStepGroup(
        DoNothing, repeat_steps=True, wait_before_repeat=_WAIT_BEFORE_REPEAT
    ),
    SingleStepGroup(UnRegisterScheduleId),
)
