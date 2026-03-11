# pylint: disable=protected-access

import pytest
from fastapi import FastAPI
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    OperationAlreadyRegisteredError,
    OperationNotFoundError,
    StepNotFoundInOperationError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    ALL_RESERVED_CONTEXT_KEYS,
    ProvidedOperationContext,
    RequiredOperationContext,
    ReservedContextKeys,
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
    async def execute(cls, app: FastAPI, required_context: RequiredOperationContext) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context


class BS1(BaseBS): ...


class BS2(BaseBS): ...


class BS3(BaseBS): ...


class MI1(BaseBS):
    @classmethod
    def wait_for_manual_intervention(cls) -> bool:
        return True


class WrongBS1C(BaseBS):
    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {"execute_key"}


class WrongBS2C(BaseBS):
    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {"execute_key"}


class WrongBS3C(BaseBS):
    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {ReservedContextKeys.SCHEDULE_ID}


class WrongBS1R(BaseBS):
    @classmethod
    def get_revert_provides_context_keys(cls) -> set[str]:
        return {"revert_key"}


class WrongBS2R(BaseBS):
    @classmethod
    def get_revert_provides_context_keys(cls) -> set[str]:
        return {"revert_key"}


class WrongBS3R(BaseBS):
    @classmethod
    def get_revert_provides_context_keys(cls) -> set[str]:
        return {ReservedContextKeys.SCHEDULE_ID}


class AllowedKeysBS(BaseBS):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {ReservedContextKeys.SCHEDULE_ID}

    @classmethod
    def get_revert_requires_context_keys(cls) -> set[str]:
        return {ReservedContextKeys.SCHEDULE_ID}


@pytest.mark.parametrize(
    "operation",
    [
        Operation(
            SingleStepGroup(BS1),
            ParallelStepGroup(BS2, BS3),
        ),
        Operation(
            SingleStepGroup(BS1),
        ),
        Operation(
            SingleStepGroup(BS1),
            SingleStepGroup(BS2),
        ),
        Operation(
            SingleStepGroup(WrongBS1C),
            SingleStepGroup(WrongBS1R),
        ),
        Operation(
            ParallelStepGroup(WrongBS2C, WrongBS2R),
        ),
        Operation(
            SingleStepGroup(BS2),
            ParallelStepGroup(BS1, BS3, repeat_steps=True),
        ),
        Operation(
            ParallelStepGroup(BS1, BS3),
            SingleStepGroup(BS2, repeat_steps=True),
        ),
        Operation(
            SingleStepGroup(BS1, repeat_steps=True),
        ),
        Operation(
            ParallelStepGroup(BS1, BS3, repeat_steps=True),
        ),
        Operation(
            SingleStepGroup(AllowedKeysBS),
        ),
    ],
)
def test_validate_operation_passes(operation: Operation):
    _validate_operation(operation)


@pytest.mark.parametrize(
    "operation, match",
    [
        (Operation(), "Operation should have at least 1 item"),
        (
            Operation(
                SingleStepGroup(BS1, repeat_steps=True),
                SingleStepGroup(BS2),
            ),
            "Only the last step group can have repeat_steps=True",
        ),
        (
            Operation(
                SingleStepGroup(BS1),
                SingleStepGroup(BS1),
            ),
            f"step_name='{BS1.__name__}' is already used in this operation",
        ),
        (
            Operation(
                ParallelStepGroup(BS2, BS2),
            ),
            f"step_name='{BS2.__name__}' is already used in this operation",
        ),
        (
            Operation(
                ParallelStepGroup(BS1),
            ),
            f"{ParallelStepGroup.__name__} needs at least 2 steps",
        ),
        (
            Operation(SingleStepGroup(WrongBS1C), SingleStepGroup(WrongBS2C)),
            f"already provided key='execute_key' in {BaseStep.get_execute_provides_context_keys.__name__}",
        ),
        (
            Operation(ParallelStepGroup(WrongBS1C, WrongBS2C)),
            f"already provided key='execute_key' in {BaseStep.get_execute_provides_context_keys.__name__}",
        ),
        (
            Operation(SingleStepGroup(WrongBS1R), SingleStepGroup(WrongBS2R)),
            f"already provided key='revert_key' in {BaseStep.get_revert_provides_context_keys.__name__}",
        ),
        (
            Operation(ParallelStepGroup(WrongBS1R, WrongBS2R)),
            f"already provided key='revert_key' in {BaseStep.get_revert_provides_context_keys.__name__}",
        ),
        (
            Operation(SingleStepGroup(MI1, repeat_steps=True)),
            "cannot have steps that require manual intervention",
        ),
        (
            Operation(
                ParallelStepGroup(MI1, BS1, BS2, repeat_steps=True),
            ),
            "cannot have steps that require manual intervention",
        ),
        (
            Operation(SingleStepGroup(WrongBS3C)),
            "which is part of reserved keys ALL_RESERVED_CONTEXT_KEYS",
        ),
        (
            Operation(SingleStepGroup(WrongBS3R)),
            "which is part of reserved keys ALL_RESERVED_CONTEXT_KEYS",
        ),
    ],
)
def test_validate_operations_fails(operation: Operation, match: str):
    with pytest.raises(ValueError, match=match):
        _validate_operation(operation)


def test_operation_registry_workflow():
    operation = Operation(SingleStepGroup(BS1))
    OperationRegistry.register("op1", operation)
    assert len(OperationRegistry._OPERATIONS) == 1  # noqa: SLF001

    assert OperationRegistry.get_operation("op1") == operation

    assert OperationRegistry.get_step("op1", "BS1") == BS1

    OperationRegistry.unregister("op1")
    assert len(OperationRegistry._OPERATIONS) == 0  # noqa: SLF001


def test_operation_registry_raises_errors():
    operation = Operation(SingleStepGroup(BS1))
    OperationRegistry.register("op1", operation)

    with pytest.raises(OperationAlreadyRegisteredError):
        OperationRegistry.register("op1", operation)

    with pytest.raises(OperationNotFoundError):
        OperationRegistry.get_operation("non_existing")

    with pytest.raises(OperationNotFoundError):
        OperationRegistry.unregister("non_existing")

    with pytest.raises(OperationNotFoundError):
        OperationRegistry.get_step("non_existing", "BS1")

    with pytest.raises(StepNotFoundInOperationError):
        OperationRegistry.get_step("op1", "non_existing")


def test_reserved_context_keys_existence():
    for e in ReservedContextKeys:
        assert e.value in ALL_RESERVED_CONTEXT_KEYS
    assert "missing_key" not in ALL_RESERVED_CONTEXT_KEYS
