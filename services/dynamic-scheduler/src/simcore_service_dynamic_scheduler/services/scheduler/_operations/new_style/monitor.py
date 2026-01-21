from ....generic_scheduler import BaseStepGroup, Operation, SingleStepGroup
from .._common_steps import DoNothing, SetCurrentScheduleId

_steps: list[BaseStepGroup] = [
    SingleStepGroup(DoNothing, repeat_steps=True),
]


def get_operation() -> Operation:
    return Operation(
        SingleStepGroup(SetCurrentScheduleId),
        *_steps,
    )
