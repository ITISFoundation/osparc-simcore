from ....generic_scheduler import Operation, SingleStepGroup
from .._common_steps import DoNothing, RegisterScheduleId, UnRegisterScheduleId

operation = Operation(
    SingleStepGroup(RegisterScheduleId),
    SingleStepGroup(DoNothing),
    SingleStepGroup(UnRegisterScheduleId),
)
