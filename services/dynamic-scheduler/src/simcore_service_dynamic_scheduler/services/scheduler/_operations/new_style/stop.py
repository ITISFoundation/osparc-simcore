from ....generic_scheduler import BaseStepGroup, Operation, SingleStepGroup
from .._common_steps import SetCurrentScheduleId, SetCurrentStateStopped

_steps: list[BaseStepGroup] = []


def get_operation() -> Operation:
    return Operation(
        SingleStepGroup(SetCurrentScheduleId),
        *_steps,
        SingleStepGroup(SetCurrentStateStopped),
        is_cancellable=False,
    )
