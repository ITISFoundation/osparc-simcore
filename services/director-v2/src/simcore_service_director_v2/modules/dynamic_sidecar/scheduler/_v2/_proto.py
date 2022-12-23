import asyncio
import inspect
import logging
import traceback
from abc import ABC, abstractmethod
from asyncio import Task
from contextlib import suppress
from functools import partial, wraps
from typing import Any, Awaitable, Callable, Iterable, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field, NonNegativeInt, validator
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


class NotAllowedContextKeyError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.key_not_allowed"
    msg_template = (
        "Provided key='{key}' is reserved for internal usage, "
        "please try using a different one."
    )


class BaseEventException(BaseV2SchedulerException):
    """use as base for all context related errors"""


class UnexpectedEventReturnTypeError(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.unexpected_event_return_type"
    msg_template = "Event should always return `dict[str, Any]`, returning: {type}"


class WorkflowAlreadyRunningException(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.workflow_already_running"
    msg_template = "Another workflow named '{workflow_name}' is already running"


class WorkflowNotFoundException(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.workflow_not_found"
    msg_template = "Workflow '{workflow_name}' not found"


class StateNotRegisteredException(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.state_not_registered"
    msg_template = (
        "Trying to start state '{state_name}' but these are the only"
        "available states {state_registry}"
    )


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


class ReservedContextKeys:
    APP: str = "app"

    WORKFLOW_NAME: str = "__workflow_name"
    WORKFLOW_STATE_NAME: str = "__workflow_state_name"
    WORKFLOW_CURRENT_EVENT_NAME: str = "__workflow_current_event_name"
    WORKFLOW_CURRENT_EVENT_INDEX: str = "__workflow_current_event_index"

    EXCEPTION: str = "_exception"

    # reserved keys cannot be overwritten by the event handlers
    RESERVED: set[str] = {
        APP,
        EXCEPTION,
        WORKFLOW_NAME,
        WORKFLOW_STATE_NAME,
        WORKFLOW_CURRENT_EVENT_NAME,
        WORKFLOW_CURRENT_EVENT_INDEX,
    }


WorkflowName = str
StateName = str
EventName = str


class ContextResolver(ContextSerializerInterface):
    """
    Used to keep track of generated data.
    """

    def __init__(
        self, app: FastAPI, workflow_name: WorkflowName, state_name: StateName
    ) -> None:
        self._app: FastAPI = app
        self._workflow_name: WorkflowName = workflow_name
        self._state_name: StateName = state_name

        self._context: ContextStorageInterface = InMemoryContext()
        self._skip_serialization: set[str] = {"app"}

    async def set(self, key: str, value: Any, *, set_reserved: bool = False) -> None:
        """
        Saves a value. Note the type of the value is forced
        at the same type as the first time this was set.

        """
        if key in ReservedContextKeys.RESERVED and not set_reserved:
            raise NotAllowedContextKeyError(key=key)

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
        await self.set(key=ReservedContextKeys.APP, value=self._app, set_reserved=True)
        await self.set(
            key=ReservedContextKeys.WORKFLOW_NAME,
            value=self._workflow_name,
            set_reserved=True,
        )
        await self.set(
            key=ReservedContextKeys.WORKFLOW_STATE_NAME,
            value=self._state_name,
            set_reserved=True,
        )

    async def shutdown(self) -> None:
        await self._context.shutdown()


### EVENT MARKERS AND DETECTION


def mark_event(func: Callable) -> Callable:
    """
    Register a coroutine as an event.
    Return type must always be of type `dict[str, Any]`
    Stores input types in `.input_types` and return type
    in `.return_type` for later usage.
    """

    func_annotations = inspect.getfullargspec(func).annotations

    # ensure output type is correct, only support sone
    return_type = func_annotations.pop("return", None)
    if return_type != dict[str, Any]:
        raise UnexpectedEventReturnTypeError(type=return_type)

    @wraps(func)
    async def wrapped(*args, **kwargs) -> Any:
        return await func(*args, **kwargs)

    # store input and return types for later usage
    wrapped.return_type = return_type
    wrapped.input_types = func_annotations

    return wrapped


### STATE PROCESSING


# state definition


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


def _get_event_and_index(
    iterable: Iterable[Callable], *, index: NonNegativeInt = 0
) -> tuple[NonNegativeInt, Callable]:
    for i, value in enumerate(iterable):
        if i >= index:
            yield i, value


class ExceptionInfo(BaseModel):
    exception_class: type
    state_name: StateName
    event_name: EventName
    serialized_traceback: str


async def workflow_runner(
    state_registry: StateRegistry,
    context_resolver: ContextResolver,
    *,
    before_event: Optional[Callable[[str, str], Awaitable[None]]] = None,
    after_event: Optional[Callable[[str, str], Awaitable[None]]] = None,
) -> None:
    """

    A workflow is a series of states that need to be ran
    NOTE: a workflow can continue or finish.
    """

    # goes through all the states defined and does tuff right?
    # not in some cases this needs to end, these are ran as tasks
    #
    state_name: StateName = await context_resolver.get(
        ReservedContextKeys.WORKFLOW_STATE_NAME, StateName
    )
    state: Optional[State] = state_registry[state_name]

    start_from_index: NonNegativeInt = 0
    try:
        start_from_index = await context_resolver.get(
            ReservedContextKeys.WORKFLOW_CURRENT_EVENT_INDEX, NonNegativeInt
        )
    except NotInContextError:
        pass

    while state is not None:
        state_name = state.name
        await context_resolver.set(
            ReservedContextKeys.WORKFLOW_STATE_NAME, state_name, set_reserved=True
        )
        logger.debug("Running state='%s', events=%s", state_name, state.events_names)
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

                event_name = event.__name__
                logger.debug("event='%s' with inputs=%s", event_name, inputs)
                # running event handler
                await context_resolver.set(
                    ReservedContextKeys.WORKFLOW_CURRENT_EVENT_NAME,
                    event_name,
                    set_reserved=True,
                )
                await context_resolver.set(
                    ReservedContextKeys.WORKFLOW_CURRENT_EVENT_INDEX,
                    index,
                    set_reserved=True,
                )

                if before_event:
                    await before_event(state_name, event_name)
                result = await event(**inputs)
                if after_event:
                    await after_event(state_name, event_name)

                # saving outputs to context
                logger.debug("event='%s', result=%s", event_name, result)
                await asyncio.gather(
                    *[
                        context_resolver.set(key=var_name, value=var_value)
                        for var_name, var_value in result.items()
                    ]
                )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected exception, deferring handling to state='%s'",
                state.on_error_state,
            )

            if state.on_error_state is None:
                # NOTE: since there is no state that takes care of the error
                # just raise it here and halt the task
                logger.error("context=%s", await context_resolver.serialize())
                raise

            # Storing exception to be possibly handled by the error state
            exception_info = ExceptionInfo(
                exception_class=e.__class__,
                state_name=await context_resolver.get(
                    ReservedContextKeys.WORKFLOW_STATE_NAME, WorkflowName
                ),
                event_name=await context_resolver.get(
                    ReservedContextKeys.WORKFLOW_CURRENT_EVENT_NAME, StateName
                ),
                serialized_traceback=traceback.format_exc(),
            )
            await context_resolver.set(
                ReservedContextKeys.EXCEPTION, exception_info, set_reserved=True
            )

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


class WorkflowManager:
    # NOTE: simply put a workflow is the graph the states generate
    # when they are run

    def __init__(
        self,
        app: FastAPI,
        state_registry: StateRegistry,
        *,
        before_event: Optional[Callable[[str, str], Awaitable[None]]] = None,
        after_event: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
        self.app = app
        self.state_registry = state_registry
        self.before_event = before_event
        self.after_event = after_event

        self._workflow_tasks: dict[WorkflowName, Task] = {}
        self._workflow_context: dict[WorkflowName, ContextResolver] = {}
        self._shutdown_tasks_workflow_context: dict[WorkflowName, Task] = {}

    async def run_workflow(
        self, workflow_name: WorkflowName, state_name: StateName
    ) -> None:
        """starts a new workflow with a unique name"""

        if workflow_name in self._workflow_context:
            raise WorkflowAlreadyRunningException(workflow_name=workflow_name)
        if state_name not in self.state_registry:
            raise StateNotRegisteredException(
                state_name=state_name, state_registry=self.state_registry
            )

        self._workflow_context[workflow_name] = context_resolver = ContextResolver(
            app=self.app, workflow_name=workflow_name, state_name=state_name
        )
        await context_resolver.start()

        workflow_runner_awaitable: Awaitable = workflow_runner(
            state_registry=self.state_registry,
            context_resolver=context_resolver,
            before_event=self.before_event,
            after_event=self.after_event,
        )

        self._create_workflow_task(workflow_runner_awaitable, workflow_name)

    async def resume_workflow(self, context_resolver: ContextResolver) -> None:
        # NOTE: expecting `await context_resolver.start()` to have already been ran

        workflow_runner_awaitable: Awaitable = workflow_runner(
            state_registry=self.state_registry,
            context_resolver=context_resolver,
            before_event=self.before_event,
            after_event=self.after_event,
        )

        workflow_name: WorkflowName = await context_resolver.get(
            ReservedContextKeys.WORKFLOW_NAME, WorkflowName
        )
        self._create_workflow_task(workflow_runner_awaitable, workflow_name)

    def _create_workflow_task(
        self, runner_awaitable: Awaitable, workflow_name: WorkflowName
    ) -> None:
        task = self._workflow_tasks[workflow_name] = asyncio.create_task(
            runner_awaitable, name=workflow_name
        )

        def workflow_complete(_: Task) -> None:
            self._workflow_tasks.pop(workflow_name, None)
            context_resolver: Optional[ContextResolver] = self._workflow_context.pop(
                workflow_name, None
            )
            if context_resolver:
                # shutting down context resolver and ensure task will not be pending
                task = self._shutdown_tasks_workflow_context[
                    workflow_name
                ] = asyncio.create_task(context_resolver.shutdown())
                task.add_done_callback(
                    partial(
                        lambda s, _: self._shutdown_tasks_workflow_context.pop(s, None),
                        workflow_name,
                    )
                )

        # remove when task is done
        task.add_done_callback(workflow_complete)

    async def wait_workflow(self, workflow_name: WorkflowName) -> None:
        """waits for workflow Task to finish"""
        if workflow_name not in self._workflow_tasks:
            raise WorkflowNotFoundException(workflow_name=workflow_name)

        task = self._workflow_tasks[workflow_name]
        await task

    @staticmethod
    async def __cancel_task(task: Optional[Task]) -> None:
        if task is None:
            return

        task.cancel()
        # TODO: better cancellation with timeout pattern as san suggested in other places
        with suppress(asyncio.CancelledError):
            await task

    async def cancel_workflow(self, workflow_name: WorkflowName) -> None:
        """cancels current workflow Task"""
        if workflow_name not in self._workflow_tasks:
            raise WorkflowNotFoundException(workflow_name=workflow_name)

        task = self._workflow_tasks[workflow_name]
        await self.__cancel_task(task)

    async def shutdown(self) -> None:
        # NOTE: content can change while iterating
        for key in self._workflow_context.keys():
            context_resolver: Optional[ContextResolver] = self._workflow_context.get(
                key, None
            )
            if context_resolver:
                await context_resolver.shutdown()

        # NOTE: content can change while iterating
        for key in self._shutdown_tasks_workflow_context.keys():
            task: Optional[Task] = self._shutdown_tasks_workflow_context.get(key, None)
            await self.__cancel_task(task)

    async def start(self) -> None:
        pass
