# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import pytest
from simcore_service_dynamic_scheduler.services.scheduler._errors import (
    UnexpectedCouldNotDetermineOperationTypeError,
)
from simcore_service_dynamic_scheduler.services.scheduler._models import OperationType
from simcore_service_dynamic_scheduler.services.scheduler._utils import (
    get_scheduler_oepration_name,
    get_scheduler_operation_type_or_raise,
)


@pytest.mark.parametrize(
    "suffix",
    [
        "1234",
        "abcd",
        "some_suffix",
        "_",
        "____",
        "___asd___Asd",
        "",
    ],
)
@pytest.mark.parametrize("operation_type", OperationType)
def test_operation_names(operation_type: OperationType, suffix: str) -> None:
    operation_name = get_scheduler_oepration_name(operation_type, suffix)
    assert operation_name == f"{operation_type}_{suffix}"
    assert get_scheduler_operation_type_or_raise(name=operation_name) == operation_type


def test_raise_on_invalid_operation_name() -> None:
    with pytest.raises(UnexpectedCouldNotDetermineOperationTypeError):
        get_scheduler_operation_type_or_raise(name="invalid_operation_name")
