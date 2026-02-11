from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Annotated, ClassVar, Final, TypeAlias, TypedDict

from fastapi import FastAPI
from pydantic import Field, NonNegativeInt, TypeAdapter, validate_call
from servicelib.deferred_tasks import DeferredContext

from ._errors import (
    OperationAlreadyRegisteredError,
    OperationNotFoundError,
    StepNotFoundInOperationError,
)
from ._models import (
    ALL_RESERVED_CONTEXT_KEYS,
    OperationName,
    ProvidedOperationContext,
    RequiredOperationContext,
    StepGroupName,
    StepName,
)

_DEFAULT_STEP_RETRIES: Final[NonNegativeInt] = 0
_DEFAULT_STEP_TIMEOUT: Final[timedelta] = timedelta(seconds=5)
_DEFAULT_WAIT_FOR_MANUAL_INTERVENTION: Final[bool] = False


class BaseStep(ABC):
    @classmethod
    def get_step_name(cls) -> StepName:
        return cls.__name__

    ### EXECUTE

    @classmethod
    @abstractmethod
    async def execute(cls, app: FastAPI, required_context: RequiredOperationContext) -> ProvidedOperationContext | None:
        """
        [mandatory] handler to be implemented with the code responsible for achieving a goal
        NOTE: Ensure this is successful if:
            - `execute` is called multiple times and does not cause duplicate resources
        """

    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        """
        [optional] keys that must be present in the OperationContext when EXECUTE is called
        """
        return set()

    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        """
        [optional] keys that will be added to the OperationContext when EXECUTE is successful
        """
        return set()

    @classmethod
    async def get_execute_retries(cls, context: DeferredContext) -> int:
        """
        [optional] amount of retires in case of creation
        HINT: you can use `get_operation_context_proxy()`, `get_step_group_proxy(context)`
            and `get_step_store_proxy(context)` to implement custom retry strategy
        """
        assert context  # nosec
        return _DEFAULT_STEP_RETRIES

    @classmethod
    async def get_execute_wait_between_attempts(cls, context: DeferredContext) -> timedelta:
        """
        [optional] wait time between retires case of creation
        HINT: you can use `get_operation_context_proxy()`, `get_step_group_proxy(context)`
            and `get_step_store_proxy(context)` to implement custom retry strategy
        """
        assert context  # nosec
        return _DEFAULT_STEP_TIMEOUT

    @classmethod
    def wait_for_manual_intervention(cls) -> bool:
        """
        [optional] if True scheduler will block waiting for manual intervention form a user
        """
        return _DEFAULT_WAIT_FOR_MANUAL_INTERVENTION

    ### REVERT

    @classmethod
    async def revert(cls, app: FastAPI, required_context: RequiredOperationContext) -> ProvidedOperationContext | None:
        """
        [optional] handler responsible for cleanup of resources executed above.
        NOTE: Ensure this is successful if:
            - `execute` is not executed
            - `execute` is executed partially
            - `revert` is called multiple times
        """
        _ = required_context
        _ = app
        return {}

    @classmethod
    def get_revert_requires_context_keys(cls) -> set[str]:
        """
        [optional] keys that must be present in the OperationContext when REVERT is called
        """
        return set()

    @classmethod
    def get_revert_provides_context_keys(cls) -> set[str]:
        """
        [optional] keys that will be added to the OperationContext when REVERT is successful
        """
        return set()

    @classmethod
    async def get_revert_retries(cls, context: DeferredContext) -> int:
        """
        [optional] amount of retires in case of failure
        HINT: you can use `get_operation_context_proxy()`, `get_step_group_proxy(context)`
            and `get_step_store_proxy(context)` to implement custom retry strategy
        """
        assert context  # nosec
        return _DEFAULT_STEP_RETRIES

    @classmethod
    async def get_revert_wait_between_attempts(cls, context: DeferredContext) -> timedelta:
        """
        [optional] timeout between retires in case of failure
        HINT: you can use `get_operation_context_proxy()`, `get_step_group_proxy(context)`
            and `get_step_store_proxy(context)` to implement custom retry strategy
        """
        assert context  # nosec
        return _DEFAULT_STEP_TIMEOUT


StepsSubGroup: TypeAlias = Annotated[tuple[type[BaseStep], ...], Field(min_length=1)]


class BaseStepGroup(ABC):
    def __init__(self, *, repeat_steps: bool, wait_before_repeat: timedelta) -> None:
        """
        if repeat_steps is True, the steps in this group will be repeated forever
        """
        self.repeat_steps = repeat_steps
        self.wait_before_repeat = wait_before_repeat

    @abstractmethod
    def __len__(self) -> int:
        """number of steps in this group"""

    @abstractmethod
    def __repr__(self) -> str:
        """text representation of this step group"""

    @abstractmethod
    def get_step_group_name(self, *, index: NonNegativeInt) -> StepGroupName:
        """returns the name of this step group"""

    @abstractmethod
    def get_step_subgroup_to_run(self) -> StepsSubGroup:
        """returns subgroups of steps to run"""


_DEFAULT_REPEAT_STEPS: Final[bool] = False
_DEFAULT_WAIT_BEFORE_REPEAT: Final[timedelta] = timedelta(seconds=5)


class SingleStepGroup(BaseStepGroup):
    def __init__(
        self,
        step: type[BaseStep],
        *,
        repeat_steps: bool = _DEFAULT_REPEAT_STEPS,
        wait_before_repeat: timedelta = _DEFAULT_WAIT_BEFORE_REPEAT,
    ) -> None:
        self._step: type[BaseStep] = step
        super().__init__(repeat_steps=repeat_steps, wait_before_repeat=wait_before_repeat)

    def __len__(self) -> int:
        return 1

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._step.get_step_name()})"

    def get_step_group_name(self, *, index: NonNegativeInt) -> StepGroupName:
        return f"{index}S{'R' if self.repeat_steps else ''}"

    def get_step_subgroup_to_run(self) -> StepsSubGroup:
        return TypeAdapter(StepsSubGroup).validate_python((self._step,))


_MIN_PARALLEL_STEPS: Final[int] = 2


class ParallelStepGroup(BaseStepGroup):
    def __init__(
        self,
        *steps: type[BaseStep],
        repeat_steps: bool = _DEFAULT_REPEAT_STEPS,
        wait_before_repeat: timedelta = _DEFAULT_WAIT_BEFORE_REPEAT,
    ) -> None:
        self._steps: list[type[BaseStep]] = list(steps)
        super().__init__(repeat_steps=repeat_steps, wait_before_repeat=wait_before_repeat)

    def __len__(self) -> int:
        return len(self._steps)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(step.get_step_name() for step in self._steps)})"

    @property
    def steps(self) -> list[type[BaseStep]]:
        return self._steps

    def get_step_group_name(self, *, index: NonNegativeInt) -> StepGroupName:
        return f"{index}P{'R' if self.repeat_steps else ''}"

    def get_step_subgroup_to_run(self) -> StepsSubGroup:
        return TypeAdapter(StepsSubGroup).validate_python(tuple(self._steps))


class Operation:
    def __init__(
        self,
        *step_groups: BaseStepGroup,
        initial_context_required_keys: set[str] | None = None,
        is_cancellable: bool = True,
    ) -> None:
        self.step_groups = list(step_groups)
        self.initial_context_required_keys = (
            set() if initial_context_required_keys is None else initial_context_required_keys
        )
        self.is_cancellable = is_cancellable

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(repr(group) for group in self.step_groups)})"


def _has_abstract_methods(cls: type[object]) -> bool:
    return bool(getattr(cls, "__abstractmethods__", set()))


@validate_call(config={"arbitrary_types_allowed": True})
def _validate_operation(  # noqa: C901, PLR0912 # pylint: disable=too-many-branches
    operation: Operation,
) -> dict[StepName, type[BaseStep]]:
    if len(operation.step_groups) == 0:
        msg = f"{Operation.__name__} should have at least 1 item"
        raise ValueError(msg)

    detected_steps_names: dict[StepName, type[BaseStep]] = {}
    execute_provided_keys: set[str] = set()
    revert_provided_keys: set[str] = set()

    for k, step_group in enumerate(operation.step_groups):
        if isinstance(step_group, ParallelStepGroup) and len(step_group.steps) < _MIN_PARALLEL_STEPS:
            msg = (
                f"{ParallelStepGroup.__name__} needs at least {_MIN_PARALLEL_STEPS} "
                f"steps. TIP: use {SingleStepGroup.__name__} instead."
            )
            raise ValueError(msg)

        if k < len(operation.step_groups) - 1 and step_group.repeat_steps is True:
            msg = f"Only the last step group can have repeat_steps=True. Error at index {k=}"
            raise ValueError(msg)

        for step in step_group.get_step_subgroup_to_run():
            step_name = step.get_step_name()

            if _has_abstract_methods(step):
                msg = f"Step {step_name=} has abstract methods and cannot be registered"
                raise ValueError(msg)

            if step_name in detected_steps_names:
                msg = f"Step {step_name=} is already used in this operation {detected_steps_names=}"
                raise ValueError(msg)

            detected_steps_names[step_name] = step

            for key in step.get_execute_provides_context_keys():
                if key in ALL_RESERVED_CONTEXT_KEYS:
                    msg = (
                        f"Step {step_name=} provides {key=} which is part of reserved keys {ALL_RESERVED_CONTEXT_KEYS=}"
                    )
                    raise ValueError(msg)
                if key in execute_provided_keys:
                    msg = (
                        f"Step {step_name=} provides already provided {key=} in "
                        f"{step.get_execute_provides_context_keys.__name__}()"
                    )
                    raise ValueError(msg)
                execute_provided_keys.add(key)

            for key in step.get_revert_provides_context_keys():
                if key in ALL_RESERVED_CONTEXT_KEYS:
                    msg = (
                        f"Step {step_name=} provides {key=} which is part of reserved keys {ALL_RESERVED_CONTEXT_KEYS=}"
                    )
                    raise ValueError(msg)
                if key in revert_provided_keys:
                    msg = (
                        f"Step {step_name=} provides already provided {key=} in "
                        f"{step.get_revert_provides_context_keys.__name__}()"
                    )
                    raise ValueError(msg)
                revert_provided_keys.add(key)

        if (
            step_group.repeat_steps is True
            and k == len(operation.step_groups) - 1
            and any(step.wait_for_manual_intervention() for step in step_group.get_step_subgroup_to_run())
        ):
            msg = (
                "Step groups with repeat_steps=True cannot have steps that require "
                "manual intervention. This would lead to a deadlock."
            )
            raise ValueError(msg)

    return detected_steps_names


def get_operation_provided_context_keys(operation: Operation) -> set[str]:
    provided_keys: set[str] = set()

    for step_group in operation.step_groups:
        for step in step_group.get_step_subgroup_to_run():
            provided_keys.update(step.get_execute_provides_context_keys())
            provided_keys.update(step.get_revert_provides_context_keys())

    return provided_keys


class _UpdateScheduleDataDict(TypedDict):
    operation: Operation
    steps: dict[StepName, type[BaseStep]]


class OperationRegistry:
    _OPERATIONS: ClassVar[dict[OperationName, _UpdateScheduleDataDict]] = {}

    @classmethod
    def register(cls, operation_name: OperationName, operation: Operation) -> None:
        steps = _validate_operation(operation)

        if operation_name in cls._OPERATIONS:
            raise OperationAlreadyRegisteredError(operation_name=operation_name)

        cls._OPERATIONS[operation_name] = {"operation": operation, "steps": steps}

    @classmethod
    def get_operation(cls, operation_name: OperationName) -> Operation:
        if operation_name not in cls._OPERATIONS:
            raise OperationNotFoundError(
                operation_name=operation_name,
                registered_operations=list(cls._OPERATIONS.keys()),
            )

        return cls._OPERATIONS[operation_name]["operation"]

    @classmethod
    def get_step(cls, operation_name: OperationName, step_name: StepName) -> type[BaseStep]:
        if operation_name not in cls._OPERATIONS:
            raise OperationNotFoundError(
                operation_name=operation_name,
                registered_operations=list(cls._OPERATIONS.keys()),
            )

        steps_names = set(cls._OPERATIONS[operation_name]["steps"].keys())
        if step_name not in steps_names:
            raise StepNotFoundInOperationError(
                step_name=step_name,
                operation_name=operation_name,
                steps_names=steps_names,
            )

        return cls._OPERATIONS[operation_name]["steps"][step_name]

    @classmethod
    def unregister(cls, operation_name: OperationName) -> None:
        if operation_name not in cls._OPERATIONS:
            raise OperationNotFoundError(
                operation_name=operation_name,
                registered_operations=list(cls._OPERATIONS.keys()),
            )

        del cls._OPERATIONS[operation_name]
