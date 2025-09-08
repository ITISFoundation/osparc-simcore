# pylint: disable=protected-access

import pytest
from fastapi import FastAPI
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    OperationAlreadyRegisteredError,
    OperationNotFoundError,
    StepNotFoundInoperationError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._operation import (
    BaseStep,
    Operation,
    OperationRegistry,
    ParallelStepGroup,
    SingleStepGroup,
    _validate_operation,
)


class BaseBS(BaseStep):
    @classmethod
    async def create(cls, app: FastAPI) -> None:
        _ = app


class BS1(BaseBS):
    pass


class BS2(BaseBS):
    pass


class BS3(BaseBS):
    pass


@pytest.mark.parametrize(
    "operation",
    [
        [
            SingleStepGroup(BS1),
            ParallelStepGroup(BS2, BS3),
        ],
        [
            SingleStepGroup(BS1),
        ],
        [
            SingleStepGroup(BS1),
            SingleStepGroup(BS2),
        ],
        [
            SingleStepGroup(BS2),
            ParallelStepGroup(BS1, BS3, repeat_steps=True),
        ],
        [
            ParallelStepGroup(BS1, BS3),
            SingleStepGroup(BS2, repeat_steps=True),
        ],
        [
            SingleStepGroup(BS1, repeat_steps=True),
        ],
        [
            ParallelStepGroup(BS1, BS3, repeat_steps=True),
        ],
    ],
)
def test_validate_operation_passes(operation: Operation):
    _validate_operation(operation)


@pytest.mark.parametrize(
    "operation, match",
    [
        ([], "List should have at least 1 item after validation"),
        (
            [
                SingleStepGroup(BS1, repeat_steps=True),
                SingleStepGroup(BS2),
            ],
            "Only the last step group can have repeat_steps=True",
        ),
        (
            [
                SingleStepGroup(BS1),
                SingleStepGroup(BS1),
            ],
            f"step_name='{BS1.__name__}' is already used in this operation",
        ),
        (
            [
                ParallelStepGroup(BS2, BS2),
            ],
            f"step_name='{BS2.__name__}' is already used in this operation",
        ),
        (
            [
                ParallelStepGroup(BS1),
            ],
            f"{ParallelStepGroup.__name__} needs at least 2 steps",
        ),
    ],
)
def test_validate_operations_fails(operation: Operation, match: str):
    with pytest.raises(ValueError, match=match):
        _validate_operation(operation)


def test_operation_registry_workflow():
    operation: Operation = [SingleStepGroup(BS1)]
    OperationRegistry.register("op1", operation)
    assert len(OperationRegistry._OPERATIONS) == 1

    assert OperationRegistry.get_operation("op1") == operation

    assert OperationRegistry.get_step("op1", "BS1") == BS1

    OperationRegistry.unregister("op1")
    assert len(OperationRegistry._OPERATIONS) == 0


def test_operation_registry_raises_errors():
    operation: Operation = [SingleStepGroup(BS1)]
    OperationRegistry.register("op1", operation)

    with pytest.raises(OperationAlreadyRegisteredError):
        OperationRegistry.register("op1", operation)

    with pytest.raises(OperationNotFoundError):
        OperationRegistry.get_operation("non_existing")

    with pytest.raises(OperationNotFoundError):
        OperationRegistry.unregister("non_existing")

    with pytest.raises(OperationNotFoundError):
        OperationRegistry.get_step("non_existing", "BS1")

    with pytest.raises(StepNotFoundInoperationError):
        OperationRegistry.get_step("op1", "non_existing")
