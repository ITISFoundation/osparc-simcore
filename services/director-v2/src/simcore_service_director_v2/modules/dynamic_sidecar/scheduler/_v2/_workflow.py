import asyncio
import logging
import traceback
from asyncio import Task
from contextlib import suppress
from functools import partial
from typing import Any, Awaitable, Callable, Iterable, Optional

from fastapi import FastAPI
from pydantic import BaseModel, NonNegativeInt

from ._context_base import ContextSerializerInterface, ReservedContextKeys
from ._context_resolver import ContextResolver
from ._errors import (
    NotInContextError,
    StateNotRegisteredException,
    WorkflowAlreadyRunningException,
    WorkflowNotFoundException,
)
from ._models import EventName, StateName, WorkflowName
from ._state import State, StateRegistry

logger = logging.getLogger(__name__)


class ExceptionInfo(BaseModel):
    exception_class: type
    state_name: StateName
    event_name: EventName
    serialized_traceback: str


def _get_event_and_index(
    iterable: Iterable[Callable], *, index: NonNegativeInt = 0
) -> tuple[NonNegativeInt, Callable]:
    for i, value in enumerate(iterable):
        if i >= index:
            yield i, value


async def workflow_runner(
    state_registry: StateRegistry,
    context_resolver: ContextResolver,
    *,
    before_event_hook: Optional[
        Callable[[StateName, EventName], Awaitable[None]]
    ] = None,
    after_event_hook: Optional[
        Callable[[StateName, EventName], Awaitable[None]]
    ] = None,
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

                if before_event_hook:
                    await before_event_hook(state_name, event_name)
                result = await event(**inputs)
                if after_event_hook:
                    await after_event_hook(state_name, event_name)

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
                logger.error("context=%s", await context_resolver.to_dict())
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
        storage_context: type[ContextSerializerInterface],
        app: FastAPI,
        state_registry: StateRegistry,
        *,
        before_event_hook: Optional[
            Callable[[StateName, EventName], Awaitable[None]]
        ] = None,
        after_event_hook: Optional[
            Callable[[StateName, EventName], Awaitable[None]]
        ] = None,
    ) -> None:
        self.storage_context = storage_context
        self.app = app
        self.state_registry = state_registry
        self.before_event_hook = before_event_hook
        self.after_event_hook = after_event_hook

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
            storage_context=self.storage_context,
            app=self.app,
            workflow_name=workflow_name,
            state_name=state_name,
        )
        await context_resolver.start()

        workflow_runner_awaitable: Awaitable = workflow_runner(
            state_registry=self.state_registry,
            context_resolver=context_resolver,
            before_event_hook=self.before_event_hook,
            after_event_hook=self.after_event_hook,
        )

        self._create_workflow_task(workflow_runner_awaitable, workflow_name)

    async def resume_workflow(self, context_resolver: ContextResolver) -> None:
        # NOTE: expecting `await context_resolver.start()` to have already been ran

        workflow_runner_awaitable: Awaitable = workflow_runner(
            state_registry=self.state_registry,
            context_resolver=context_resolver,
            before_event_hook=self.before_event_hook,
            after_event_hook=self.after_event_hook,
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
