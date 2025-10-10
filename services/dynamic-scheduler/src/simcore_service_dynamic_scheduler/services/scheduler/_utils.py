from ._error import UnexpectedCouldNotDetermineOperationTypeError
from ._models import OperationType, SchedulerOperationName


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
