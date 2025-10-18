from typing import Final

from pydantic import NonNegativeInt

from ...generic_scheduler import Operation, OperationRegistry, SingleStepGroup
from .. import _opration_names
from . import enforce, legacy, new_style
from ._common_steps import RegisterScheduleId, UnRegisterScheduleId

_MIN_STEPS_IN_OPERATION: Final[NonNegativeInt] = 3


def _validate_operation(operation: Operation, *, is_monitor: bool) -> None:
    min_steps = _MIN_STEPS_IN_OPERATION - 1 if is_monitor else _MIN_STEPS_IN_OPERATION
    if len(operation.step_groups) < min_steps:
        msg = (
            f"Operation must have at least {min_steps} "
            f"startign with {RegisterScheduleId.__name__} and "
            f"ending with {UnRegisterScheduleId.__name__}, "
            f"got: {operation.step_groups}"
        )
        raise ValueError(msg)
    first_step_group = operation.step_groups[0]

    if (
        isinstance(first_step_group, SingleStepGroup)
        and first_step_group.get_step_subgroup_to_run()[0] is not RegisterScheduleId
    ):
        msg = (
            f"First step group must be {RegisterScheduleId.__name__}, "
            f"got: {first_step_group}"
        )
        raise ValueError(msg)

    if is_monitor:
        # does not require last step group, since the unregistration of schedule_id
        # will be done via RegisterScheduleId's revert
        return

    last_step_group = operation.step_groups[-1]
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
    for opration_name, operation, is_monitor in (
        (_opration_names.ENFORCE, enforce.get_operation(), False),
        (_opration_names.LEGACY_MONITOR, legacy.monitor.get_operation(), True),
        (_opration_names.LEGACY_START, legacy.start.get_operation(), False),
        (_opration_names.LEGACY_STOP, legacy.stop.get_operation(), False),
        (_opration_names.NEW_STYLE_MONITOR, new_style.monitor.get_operation(), True),
        (_opration_names.NEW_STYLE_START, new_style.start.get_operation(), False),
        (_opration_names.NEW_STYLE_STOP, new_style.start.get_operation(), False),
    ):
        _validate_operation(operation, is_monitor=is_monitor)
        OperationRegistry.register(opration_name, operation)


def unregister_operations() -> None:
    OperationRegistry.unregister(_opration_names.ENFORCE)
    OperationRegistry.unregister(_opration_names.LEGACY_MONITOR)
    OperationRegistry.unregister(_opration_names.LEGACY_START)
    OperationRegistry.unregister(_opration_names.LEGACY_STOP)
    OperationRegistry.unregister(_opration_names.NEW_STYLE_MONITOR)
    OperationRegistry.unregister(_opration_names.NEW_STYLE_START)
    OperationRegistry.unregister(_opration_names.NEW_STYLE_STOP)
