from ....generic_scheduler import BaseStepGroup, Operation, SingleStepGroup
from .._common_steps import (
    RegisterScheduleId,
    SetCurrentStateRunning,
    UnRegisterScheduleId,
)

_steps: list[BaseStepGroup] = []


def get_operation() -> Operation:
    return Operation(
        SingleStepGroup(RegisterScheduleId),
        *_steps,
        SingleStepGroup(SetCurrentStateRunning),
        SingleStepGroup(UnRegisterScheduleId),
    )
