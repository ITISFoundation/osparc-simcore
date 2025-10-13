from typing import Final

from pydantic import NonNegativeInt

from ..generic_scheduler import Operation, SingleStepGroup
from ._errors import UnexpectedCouldNotDetermineOperationTypeError
from ._models import OperationType, SchedulerOperationName
from ._operations._common_steps import RegisterScheduleId, UnRegisterScheduleId

_MIN_STEPS_IN_OPERATION: Final[NonNegativeInt] = 3


def get_scheduler_oepration_name(
    operation_type: OperationType, suffix: str
) -> SchedulerOperationName:
    return SchedulerOperationName(f"{operation_type.value}_{suffix}")


def get_scheduler_operation_type_or_raise(
    *,
    name: SchedulerOperationName,
) -> OperationType:
    operation_type = name.split("_")
    try:
        return OperationType(operation_type[:1][0])
    except ValueError as exc:
        # NOTE: if this is raised there is an actual issue with the operation name
        raise UnexpectedCouldNotDetermineOperationTypeError(
            operation_name=name, supported_types={x.value for x in OperationType}
        ) from exc


def validate_operation(operation: Operation) -> None:
    if len(operation.step_groups) < _MIN_STEPS_IN_OPERATION:
        msg = (
            f"Operation must have at least {_MIN_STEPS_IN_OPERATION} "
            f"startign with {RegisterScheduleId.__name__} and "
            f"ending with {UnRegisterScheduleId.__name__}, "
            f"got: {operation.step_groups}"
        )
        raise ValueError(msg)
    first_step_group = operation.step_groups[0]
    last_step_group = operation.step_groups[-1]

    if (
        isinstance(first_step_group, SingleStepGroup)
        and first_step_group.get_step_subgroup_to_run()[0] is not RegisterScheduleId
    ):
        msg = (
            f"First step group must be {RegisterScheduleId.__name__}, "
            f"got: {first_step_group}"
        )
        raise ValueError(msg)

    if (
        isinstance(last_step_group, SingleStepGroup)
        and last_step_group.get_step_subgroup_to_run()[0] is not UnRegisterScheduleId
    ):
        msg = (
            f"Last step group must be {UnRegisterScheduleId.__name__}, "
            f"got: {last_step_group}"
        )
        raise ValueError(msg)
