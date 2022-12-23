import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from asyncio import Task
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Iterable, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field, NonNegativeInt, parse_obj_as, validator
from pydantic.errors import PydanticErrorMixin

logger = logging.getLogger(__name__)
### ERRORS


class BaseV2SchedulerException(PydanticErrorMixin, RuntimeError):
    """base for all exceptions here"""


class BaseContextException(BaseV2SchedulerException):
    """use as base for all context related errors"""


class NotInContextError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.not_in_context"
    msg_template = "Could not find a variable named '{key}' in context: {context}"


class SetTypeMismatchError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.set_type_mismatch"
    msg_template = (
        "Found a variable named '{key}' of type='{existing_type}' and value="
        "'{existing_value}'. Trying to set to type='{new_type}' and value="
        "'{new_value}'"
    )


class GetTypeMismatchError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.get_type_mismatch"
    msg_template = (
        "Found a variable named '{key}' of type='{existing_type}' and value="
        "'{existing_value}'. Expecting type='{expected_type}'"
    )


class BaseEventException(BaseV2SchedulerException):
    """use as base for all context related errors"""


class UnexpectedEventReturnTypeError(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.unexpected_event_return_type"
    msg_template = "Event should always return `dict[str, Any]`, returning: {type}"


class WorkflowAlreadyRunningException(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.workflow_already_running"
    msg_template = "Another workflow named '{workflow}' is already running"


### CONTEXT


class ContextSerializerInterface(ABC):
    @abstractmethod
    async def serialize(self) -> dict[str, Any]:
        """returns the context of a store as a dictionary"""

    @abstractmethod
    async def deserialize(self, incoming: dict[str, Any]) -> None:
        """parses the incoming context and sends it to the store"""


class ContextStorageInterface(ABC):
    """
    Base interface for saving and loading data.
    """

    @abstractmethod
    async def save(self, key: str, value: Any) -> None:
        """saves value to sore"""

    @abstractmethod
    async def load(self, key: str) -> Optional[Any]:
        """load value from store"""

    @abstractmethod
    async def has_key(self, key: str) -> bool:
        """is True if key is in store"""

    @abstractmethod
    async def start(self) -> None:
        """run storage specific initializers"""

    @abstractmethod
    async def shutdown(self) -> None:
        """run storage specific halt and cleanup"""


class InMemoryContext(ContextStorageInterface, ContextSerializerInterface):
    def __init__(self) -> None:
        self._context: dict[str, Any] = {}

    async def save(self, key: str, value: Any) -> None:
        self._context[key] = value

    async def load(self, key: str) -> Optional[Any]:
        return self._context[key]

    async def has_key(self, key: str) -> bool:
        return key in self._context

    async def serialize(self) -> dict[str, Any]:
        return self._context

    async def deserialize(self, incoming: dict[str, Any]) -> None:
        self._context.update(incoming)

    async def start(self) -> None:
        """nothing to do here"""

    async def shutdown(self) -> None:
        """nothing to do here"""


class ContextResolver(ContextSerializerInterface):
    """
    Used to keep track of generated data.
    """

    def __init__(self, app: FastAPI) -> None:
        self._app: FastAPI = app

        self._context: ContextStorageInterface = InMemoryContext()
        self._skip_serialization: set[str] = {"app"}

    async def set(self, key: str, value: Any) -> None:
        """
        Saves a value. Note the type of the value is forced
        at the same type as the first time this was set.
        """
        if await self._context.has_key(key):
            # if a value previously existed,
            # ensure it has the same type
            existing_value = await self._context.load(key)
            existing_type = type(existing_value)
            value_type = type(value)

            if existing_type != value_type:
                raise SetTypeMismatchError(
                    key=key,
                    existing_value=existing_value,
                    existing_type=existing_type,
                    new_value=value,
                    new_type=value_type,
                )

        await self._context.save(key, value)

    async def get(self, key: str, expected_type: type) -> Optional[Any]:
        """
        returns an existing value ora raises an error
        """
        if not await self._context.has_key(key):
            raise NotInContextError(key=key, context=await self._context.serialize())

        existing_value = await self._context.load(key)
        exiting_type = type(existing_value)
        if exiting_type != expected_type:
            raise GetTypeMismatchError(
                key=key,
                existing_value=existing_value,
                exiting_type=exiting_type,
                expected_type=expected_type,
            )
        return existing_value

    async def serialize(self) -> dict[str, Any]:
        return await self._context.serialize()

    async def deserialize(self, incoming: dict[str, Any]) -> None:
        return await self._context.deserialize(incoming)

    async def start(self) -> None:
        await self._context.start()
        # adding app to context
        await self.set(key="app", value=self._app)

    async def shutdown(self) -> None:
        await self._context.shutdown()


### EVENT MARKERS AND DETECTION

# TODO: add parameters to support a retry policy,
# like the one From tenacity!
def mark_event(func: Callable) -> Callable:
    """
    Register a coroutine as an event.
    Return type must always be of type `dict[str, Any]`
    Stores input types in `.input_types` attribute for later usage.
    """

    func_annotations = inspect.getfullargspec(func).annotations

    # ensure output type is correct, only support sone
    return_type = func_annotations.pop("return", None)
    if return_type != dict[str, Any]:
        raise UnexpectedEventReturnTypeError(type=return_type)

    @wraps(func)
    async def wrapped(*args, **kwargs) -> Any:
        return await func(*args, **kwargs)

    # store inputs for later usage
    wrapped.return_type = return_type
    wrapped.input_types = func_annotations

    return wrapped


### STATE PROCESSING


# state definition

WorkflowName = str
StateName = str
EventName = str


class State(BaseModel):
    name: str = Field(..., description="Name of the state, required to identify them")
    events: list[Callable] = Field(
        ...,
        description=(
            "list of functions marked as events, the order in this list "
            "is the order in which events will be executed"
        ),
    )

    next_state: Optional[StateName] = Field(
        ...,
        description="name of the state to run after this state",
    )
    on_error_state: Optional[StateName] = Field(
        ...,
        description="name of the state to run after this state raises an unexpected error",
    )

    @property
    def events_names(self) -> list[str]:
        return [x.__name__ for x in self.events]

    @validator("events")
    @classmethod
    def ensure_all_marked_as_event(cls, events):
        for event in events:
            for attr_name in ("input_types", "return_type"):
                if not hasattr(event, attr_name):
                    raise ValueError(
                        f"Event handler {event.__name__} should expose `{attr_name}` attribute. Was it decorated with @mark_event?"
                    )
            if type(getattr(event, "input_types")) != dict:
                raise ValueError(
                    f"`{event.__name__}.input_types` should be of type {dict}"
                )
            if getattr(event, "return_type") != dict[str, Any]:
                raise ValueError(
                    f"`{event.__name__}.return_type` should be of type {dict[str, Any]}"
                )
        return events


class StateRegistry:
    def __init__(self, *states: State) -> None:
        self._registry: dict[str, State] = {x.name: x for x in states}

    def __contains__(self, item: str) -> bool:
        return item in self._registry

    def __getitem__(self, key: str) -> State:
        return self._registry[key]


# WORKFLOW


class WorkflowTracker(BaseModel):
    """
    Contains information relative to internals required to
    handle a workflow.
    """

    name: WorkflowName  # required
    state: StateName  # required

    current_event: Optional[EventName] = None
    current_event_index: Optional[NonNegativeInt] = None


def _get_event_and_index(
    iterable: Iterable[Callable], *, index: NonNegativeInt = 0
) -> tuple[NonNegativeInt, Callable]:
    for i, value in enumerate(iterable):
        if i >= index:
            yield i, value


async def workflow_runner(
    state_registry: StateRegistry,
    context_resolver: ContextResolver,
    workflow_tracker: WorkflowTracker,
    # TODO: optional async callbacks for when the events stat and finish?
) -> None:
    """

    A workflow is a series of states that need to be ran
    NOTE: a workflow can continue or finish.
    """

    # goes through all the states defined and does tuff right?
    # not in some cases this needs to end, these are ran as tasks
    #
    state: Optional[State] = state_registry[workflow_tracker.state]
    start_from_index = (
        0
        if workflow_tracker.current_event_index is None
        else workflow_tracker.current_event_index
    )

    while state is not None:
        workflow_tracker.state = state.name
        logger.debug(
            "Running state='%s', events=%s", workflow_tracker.state, state.events_names
        )
        try:
            for index, event in _get_event_and_index(
                state.events, index=start_from_index
            ):
                # fetching inputs from context
                inputs: dict[str, Any] = {}
                if event.input_types:
                    get_inputs_results = await asyncio.gather(
                        *[
                            context_resolver.get(var_name, var_type)
                            for var_name, var_type in event.input_types.items()
                        ]
                    )
                    inputs = dict(zip(event.input_types, get_inputs_results))
                logger.debug(
                    "event='%s' with inputs=%s", workflow_tracker.current_event, inputs
                )

                # running event handler
                workflow_tracker.current_event = event.__name__
                workflow_tracker.current_event_index = index
                result = await event(**inputs)

                # saving outputs to context
                logger.debug(
                    "event='%s', result=%s", workflow_tracker.current_event, result
                )
                await asyncio.gather(
                    *[
                        context_resolver.set(key=var_name, value=var_value)
                        for var_name, var_value in result.items()
                    ]
                )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "An unexpected exception was detected, deferring execution to state=%s",
                state.on_error_state,
            )

            if state.on_error_state is None:
                # NOTE: since there is no state that takes care of the error
                # just raise it here and halt the task
                raise

            # TODO: the exception need to be passed somehow in here, injected via
            # Context
            # TODO: injected exception needs to be serializable somehow!
            # figure out how to handle this issue!
            # that for sure since it excepts to pull it from the input!

            state = (
                None
                if state.on_error_state is None
                else state_registry[state.on_error_state]
            )
        else:
            state = (
                None if state.next_state is None else state_registry[state.next_state]
            )
        finally:
            start_from_index = 0

    logger.debug("Done with workflow")


### Cancellable workflow and workflow switching


@dataclass
class WorkflowState:
    # data generated by the states and their events
    context_resolver: ContextResolver
    # data relative to internals and required for resuming upon error
    workflow_tracker: WorkflowTracker

    async def deserialize(self, incoming: dict[str, Any]) -> None:
        self.context_resolver.deserialize(incoming["context"])
        self.workflow_tracker = parse_obj_as(
            WorkflowTracker, incoming["workflow_tracker"]
        )

    async def serialize(
        self,
    ) -> dict[str, Any]:
        return dict(
            context=await self.context_resolver.serialize(),
            workflow_tracker=self.workflow_tracker.dict(),
        )


class WorkflowManager:
    # NOTE: simply put a workflow is the graph the states generate
    # when they are run

    def __init__(self, app: FastAPI, state_registry: StateRegistry) -> None:
        self.app: FastAPI = app
        self.state_registry: StateRegistry = state_registry
        self._workflow_tasks: dict[WorkflowName, Task] = {}
        self._workflow_states: dict[WorkflowName, WorkflowState] = {}

    async def start_or_resume_workflow(
        self,
        name: WorkflowName,
        state_name: StateName,
        *,
        workflow_state: Optional[WorkflowState] = None,
    ) -> None:
        # TODO: maybe split into two separate handlers
        # one for start and one for resume!

        if name not in self._workflow_tasks:
            raise WorkflowAlreadyRunningException(workflow=name)

        if workflow_state is None:
            context_resolver = ContextResolver(app=self.app)
            workflow_tracker = WorkflowTracker(name=name, state=state_name)
            await context_resolver.start()
            # TODO start this as a task
            workflow_runner(
                state_registry=self.state_registry,
                context_resolver=context_resolver,
                workflow_tracker=workflow_tracker,
            )
        else:
            # TODO start this as a task
            workflow_runner(
                state_registry=self.state_registry,
                context_resolver=workflow_state.context_resolver,
                workflow_tracker=workflow_state.workflow_tracker,
            )

        # TODO: append done callbacks to remove it when the workflow is completed
        # This way we know if something went wrong with it

    async def wait_workflow(self, name: WorkflowName) -> None:
        """waits for workflow Task to finish"""

    async def cancel_workflow(self, name: WorkflowName) -> None:
        """cancels current workflow Task"""

    async def start(self) -> None:
        pass

    async def shutdown(self) -> None:
        # shutting down all context_resolver instances
        for workflow_state in self._workflow_states.values():
            await workflow_state.context_resolver.shutdown()
