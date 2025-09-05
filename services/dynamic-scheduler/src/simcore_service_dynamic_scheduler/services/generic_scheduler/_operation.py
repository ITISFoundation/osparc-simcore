from abc import ABC, abstractmethod
from typing import Annotated, ClassVar, Final, TypeAlias, TypedDict

from fastapi import FastAPI
from pydantic import Field, NonNegativeInt, TypeAdapter, validate_call

from ._errors import (
    OperationAlreadyRegisteredError,
    OperationNotFoundError,
    StepNotFoundInoperationError,
)
from ._models import OperationName, StepGroupName, StepName


class BaseStep(ABC):
    @classmethod
    def get_step_name(cls) -> StepName:
        return cls.__name__

    @classmethod
    @abstractmethod
    async def create(cls, app: FastAPI) -> None:
        """
        [mandatory] handler to be implemented with the code resposible for achieving a goal
        """

    @classmethod
    async def destroy(cls, app: FastAPI) -> None:
        """
        [optional] handler resposible for celanup of resources created above.
        NOTE: Ensure this is successful if:
            - `create` is not executed
            - `create` is executed partially
            - `destory` is called multiple times
        """
        _ = app


StepsSubGroup: TypeAlias = Annotated[tuple[type[BaseStep], ...], Field(min_length=1)]


class BaseStepGroup(ABC):
    def __init__(self, *, repeat_steps: bool) -> None:
        """
        if repeat_steps is True, the steps in this group will be repeated forever
        """
        self.repeat_steps = repeat_steps

    @abstractmethod
    def get_step_group_name(self, *, index: NonNegativeInt) -> StepGroupName:
        """returns the name of this step group"""

    @abstractmethod
    def get_steps_names(self) -> list[StepName]:
        """return sorted list of StepName"""

    @abstractmethod
    def get_step_subgroup_to_run(self) -> StepsSubGroup:
        """returns subgroups of steps to run"""


class SingleStepGroup(BaseStepGroup):
    def __init__(self, step: type[BaseStep], *, repeat_steps: bool = False) -> None:
        self._step: type[BaseStep] = step
        super().__init__(repeat_steps=repeat_steps)

    def get_step_group_name(self, *, index: NonNegativeInt) -> StepGroupName:
        return f"{index}S{'R' if self.repeat_steps else ''}"

    def get_steps_names(self) -> list[StepName]:
        return [self._step.get_step_name()]

    def get_step_subgroup_to_run(self) -> StepsSubGroup:
        return TypeAdapter(StepsSubGroup).validate_python((self._step,))


_MIN_PARALLEL_STEPS: Final[int] = 2


class ParallelStepGroup(BaseStepGroup):
    def __init__(self, *steps: type[BaseStep], repeat_steps: bool = False) -> None:

        self._steps: list[type[BaseStep]] = list(steps)

        super().__init__(repeat_steps=repeat_steps)

    @property
    def steps(self) -> list[type[BaseStep]]:
        return self._steps

    def get_step_group_name(self, *, index: NonNegativeInt) -> StepGroupName:
        return f"{index}P{'R' if self.repeat_steps else ''}"

    def get_steps_names(self) -> list[StepName]:
        return sorted(x.get_step_name() for x in self._steps)

    def get_step_subgroup_to_run(self) -> StepsSubGroup:
        return TypeAdapter(StepsSubGroup).validate_python(tuple(self._steps))


Operation: TypeAlias = Annotated[list[BaseStepGroup], Field(min_length=1)]


@validate_call(config={"arbitrary_types_allowed": True})
def _validate_operation(operation: Operation) -> dict[StepName, type[BaseStep]]:
    detected_steps_names: dict[StepName, type[BaseStep]] = {}

    for k, step_group in enumerate(operation):
        if isinstance(step_group, ParallelStepGroup):
            if len(step_group.steps) < _MIN_PARALLEL_STEPS:
                msg = (
                    f"{ParallelStepGroup.__name__} needs at least {_MIN_PARALLEL_STEPS} "
                    f"steps. TIP: use {SingleStepGroup.__name__} instead."
                )
                raise ValueError(msg)

        if k < len(operation) - 1 and step_group.repeat_steps is True:
            msg = f"Only the last step group can have repeat_steps=True. Error at index {k=}"
            raise ValueError(msg)

        for step in step_group.get_step_subgroup_to_run():
            step_name = step.get_step_name()

            if step_name in detected_steps_names:
                msg = f"Step {step_name=} is already used in this operation {detected_steps_names=}"
                raise ValueError(msg)

            detected_steps_names[step_name] = step

    return detected_steps_names


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
                registerd_operations=list(cls._OPERATIONS.keys()),
            )

        return cls._OPERATIONS[operation_name]["operation"]

    @classmethod
    def get_step(
        cls, operation_name: OperationName, step_name: StepName
    ) -> type[BaseStep]:
        if operation_name not in cls._OPERATIONS:
            raise OperationNotFoundError(
                operation_name=operation_name,
                registerd_operations=list(cls._OPERATIONS.keys()),
            )

        steps_names = list(cls._OPERATIONS[operation_name]["steps"].keys())
        if step_name not in steps_names:
            raise StepNotFoundInoperationError(
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
                registerd_operations=list(cls._OPERATIONS.keys()),
            )

        del cls._OPERATIONS[operation_name]
