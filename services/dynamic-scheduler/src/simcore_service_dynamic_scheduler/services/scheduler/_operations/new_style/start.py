from ....generic_scheduler import BaseStepGroup, Operation, SingleStepGroup
from .._common_steps import SetCurrentScheduleId, SetCurrentStateRunning

_steps: list[BaseStepGroup] = []


def get_operation() -> Operation:
    return Operation(
        SingleStepGroup(SetCurrentScheduleId),
        *_steps,
        SingleStepGroup(SetCurrentStateRunning),
    )
