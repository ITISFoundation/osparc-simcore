from ....generic_scheduler import BaseStepGroup, Operation, SingleStepGroup
from .._common_steps import (
    RegisterScheduleId,
    SetCurrentStateStopped,
    UnRegisterScheduleId,
)

_steps: list[BaseStepGroup] = []


def get_operation() -> Operation:
    return Operation(
        SingleStepGroup(RegisterScheduleId),
        *_steps,
        SingleStepGroup(SetCurrentStateStopped),
        SingleStepGroup(UnRegisterScheduleId),
        is_cancellable=False,
    )
