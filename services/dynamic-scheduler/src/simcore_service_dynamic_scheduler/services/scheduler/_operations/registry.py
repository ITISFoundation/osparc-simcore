from typing import Final

from pydantic import NonNegativeInt

from ...generic_scheduler import Operation, OperationRegistry, SingleStepGroup
from .. import _opration_names
from . import enforce
from ._common_steps import SetCurrentScheduleId
from .profiles import RegsteredSchedulingProfiles

_MIN_STEPS_IN_OPERATION: Final[NonNegativeInt] = 2


def _validate_operation(operation: Operation) -> None:
    if len(operation.step_groups) < _MIN_STEPS_IN_OPERATION:
        msg = (
            f"Operation must have at least {_MIN_STEPS_IN_OPERATION} "
            f"startign with {SetCurrentScheduleId.__name__} "
            f"got: {operation.step_groups}"
        )
        raise ValueError(msg)
    first_step_group = operation.step_groups[0]

    if (
        isinstance(first_step_group, SingleStepGroup)
        and first_step_group.get_step_subgroup_to_run()[0] is not SetCurrentScheduleId
    ):
        msg = (
            f"First step group must be {SetCurrentScheduleId.__name__}, "
            f"got: {first_step_group}"
        )
        raise ValueError(msg)


def register_operataions() -> None:
    # register utility operations
    for opration_name, operation in (
        (_opration_names.ENFORCE, enforce.get_operation()),
    ):
        _validate_operation(operation)
        OperationRegistry.register(opration_name, operation)

    # register scheduling profiles operations
    for profile in RegsteredSchedulingProfiles.iter_profiles():
        for opration_name, operation in (
            (profile.start_name, profile.start_operation),
            (profile.monitor_name, profile.monitor_operation),
            (profile.stop_name, profile.stop_operation),
        ):
            _validate_operation(operation)
            OperationRegistry.register(opration_name, operation)


def unregister_operations() -> None:
    # unregister utility operations
    OperationRegistry.unregister(_opration_names.ENFORCE)

    # unregister scheduling profiles operations
    for profile in RegsteredSchedulingProfiles.iter_profiles():
        for opration_name in (
            profile.start_name,
            profile.monitor_name,
            profile.stop_name,
        ):
            OperationRegistry.unregister(opration_name)
