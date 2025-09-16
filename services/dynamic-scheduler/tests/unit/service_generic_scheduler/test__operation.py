# pylint: disable=protected-access

import pytest
from fastapi import FastAPI
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    OperationAlreadyRegisteredError,
    OperationNotFoundError,
    StepNotFoundInoperationError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    ProvidedOperationContext,
    RequiredOperationContext,
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
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context


class BS1(BaseBS): ...


class BS2(BaseBS): ...


class BS3(BaseBS): ...


class WrongBS1C(BaseBS):
    @classmethod
    def create_provides_operation_context_keys(cls) -> set[str]:
        return {"c"}


class WrongBS2C(BaseBS):
    @classmethod
    def create_provides_operation_context_keys(cls) -> set[str]:
        return {"c"}


class WrongBS1R(BaseBS):
    @classmethod
    def revert_provides_operation_context_keys(cls) -> set[str]:
        return {"r"}


class WrongBS2R(BaseBS):
    @classmethod
    def revert_provides_operation_context_keys(cls) -> set[str]:
        return {"r"}


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
            SingleStepGroup(WrongBS1C),
            SingleStepGroup(WrongBS1R),
        ],
        [
            ParallelStepGroup(WrongBS2C, WrongBS2R),
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
        (
            [SingleStepGroup(WrongBS1C), SingleStepGroup(WrongBS2C)],
            f"in {BaseStep.create_provides_operation_context_keys.__name__}",
        ),
        (
            [ParallelStepGroup(WrongBS1C, WrongBS2C)],
            f"in {BaseStep.create_provides_operation_context_keys.__name__}",
        ),
        (
            [SingleStepGroup(WrongBS1R), SingleStepGroup(WrongBS2R)],
            f"in {BaseStep.revert_provides_operation_context_keys.__name__}",
        ),
        (
            [ParallelStepGroup(WrongBS1R, WrongBS2R)],
            f"in {BaseStep.revert_provides_operation_context_keys.__name__}",
        ),
    ],
)
def test_validate_operations_fails(operation: Operation, match: str):
    with pytest.raises(ValueError, match=match):
        _validate_operation(operation)


def test_operation_registry_workflow():
    operation: Operation = [SingleStepGroup(BS1)]
    OperationRegistry.register("op1", operation)
    assert len(OperationRegistry._OPERATIONS) == 1  # noqa: SLF001

    assert OperationRegistry.get_operation("op1") == operation

    assert OperationRegistry.get_step("op1", "BS1") == BS1

    OperationRegistry.unregister("op1")
    assert len(OperationRegistry._OPERATIONS) == 0  # noqa: SLF001


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
