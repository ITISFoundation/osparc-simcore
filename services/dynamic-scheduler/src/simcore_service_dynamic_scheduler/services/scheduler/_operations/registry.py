from typing import Final

from pydantic import NonNegativeInt

from ...generic_scheduler import Operation, OperationRegistry, SingleStepGroup
from .. import _opration_names
from . import enforce, legacy, new_style
from ._common_steps import RegisterScheduleId, UnRegisterScheduleId

_MIN_STEPS_IN_OPERATION: Final[NonNegativeInt] = 3


def _validate_operation(operation: Operation) -> None:
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


def register_operataions() -> None:
    for opration_name, operation in (
        (_opration_names.ENFORCE, enforce.operation),
        (_opration_names.LEGACY_MONITOR, legacy.monitor.operation),
        (_opration_names.LEGACY_START, legacy.start.operation),
        (_opration_names.LEGACY_STOP, legacy.stop.operation),
        (_opration_names.NEW_STYLE_MONITOR, new_style.monitor.operation),
        (_opration_names.NEW_STYLE_START, new_style.start.operation),
        (_opration_names.NEW_STYLE_STOP, new_style.start.operation),
    ):
        _validate_operation(operation)
        OperationRegistry.register(opration_name, operation)


def unregister_operations() -> None:
    OperationRegistry.unregister(_opration_names.ENFORCE)
    OperationRegistry.unregister(_opration_names.LEGACY_MONITOR)
    OperationRegistry.unregister(_opration_names.LEGACY_START)
    OperationRegistry.unregister(_opration_names.LEGACY_STOP)
    OperationRegistry.unregister(_opration_names.NEW_STYLE_MONITOR)
    OperationRegistry.unregister(_opration_names.NEW_STYLE_START)
    OperationRegistry.unregister(_opration_names.NEW_STYLE_STOP)
