import asyncio
import logging
import traceback
from asyncio import Task
from contextlib import suppress
from functools import partial
from typing import Any, Awaitable, Callable, Iterable, Optional

from fastapi import FastAPI
from pydantic import BaseModel, NonNegativeInt

from ._action import Action
from ._context_base import ContextInterface, ReservedContextKeys
from ._errors import (
    ActionNotRegisteredException,
    NotInContextError,
    PlayAlreadyRunningException,
    PlayNotFoundException,
)
from ._models import ActionName, StepName, WorkflowName
from ._workflow import Workflow
from ._workflow_context import WorkflowContext

logger = logging.getLogger(__name__)


class ExceptionInfo(BaseModel):
    exception_class: type
    action_name: ActionName
    step_name: StepName
    serialized_traceback: str


def _iter_index_step(
    iterable: Iterable[Callable], *, index: NonNegativeInt = 0
) -> Iterable[tuple[NonNegativeInt, Callable]]:
    for i, value in enumerate(iterable):
        if i >= index:
            yield i, value


async def action_player(
    workflow: Workflow,
    workflow_context: WorkflowContext,
    *,
    before_step_hook: Optional[
        Callable[[ActionName, StepName], Awaitable[None]]
    ] = None,
    after_step_hook: Optional[Callable[[ActionName, StepName], Awaitable[None]]] = None,
) -> None:
    """
    Given a `PlayCatalog` and a `PlayContext` runs from a given
    starting action.
    Can also recover from an already initialized `PlayContext`.
    """

    # goes through all the states defined and does tuff right?
    # not in some cases this needs to end, these are ran as tasks
    #
    action_name: ActionName = await workflow_context.get(
        ReservedContextKeys.PLAY_ACTION_NAME, ActionName
    )
    action: Optional[Action] = workflow[action_name]

    start_from_index: int = 0
    try:
        start_from_index = await workflow_context.get(
            ReservedContextKeys.PLAY_CURRENT_STEP_INDEX, int
        )
    except NotInContextError:
        pass

    while action is not None:
        action_name = action.name
        await workflow_context.set(
            ReservedContextKeys.PLAY_ACTION_NAME, action_name, set_reserved=True
        )
        logger.debug("Running action='%s', step=%s", action_name, action.steps_names)
        try:
            for index, step in _iter_index_step(action.steps, index=start_from_index):
                step_name = step.__name__

                if before_step_hook:
                    await before_step_hook(action_name, step_name)

                # fetching inputs from context
                inputs: dict[str, Any] = {}
                if step.input_types:
                    get_inputs_results = await asyncio.gather(
                        *[
                            workflow_context.get(var_name, var_type)
                            for var_name, var_type in step.input_types.items()
                        ]
                    )
                    inputs = dict(zip(step.input_types, get_inputs_results))
                logger.debug("step='%s' inputs=%s", step_name, inputs)

                # running event handler
                await workflow_context.set(
                    ReservedContextKeys.PLAY_CURRENT_STEP_NAME,
                    step_name,
                    set_reserved=True,
                )
                await workflow_context.set(
                    ReservedContextKeys.PLAY_CURRENT_STEP_INDEX,
                    index,
                    set_reserved=True,
                )
                result = await step(**inputs)

                # saving outputs to context
                logger.debug("step='%s' result=%s", step_name, result)
                await asyncio.gather(
                    *[
                        workflow_context.set(key=var_name, value=var_value)
                        for var_name, var_value in result.items()
                    ]
                )

                if after_step_hook:
                    await after_step_hook(action_name, step_name)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected exception, deferring handling to action='%s'",
                action.on_error_action,
            )

            if action.on_error_action is None:
                # NOTE: since there is no state that takes care of the error
                # just raise it here and halt the task
                logger.error("workflow_context=%s", await workflow_context.to_dict())
                raise

            # Storing exception to be possibly handled by the error state
            exception_info = ExceptionInfo(
                exception_class=e.__class__,
                action_name=await workflow_context.get(
                    ReservedContextKeys.PLAY_ACTION_NAME, WorkflowName
                ),
                step_name=await workflow_context.get(
                    ReservedContextKeys.PLAY_CURRENT_STEP_NAME, ActionName
                ),
                serialized_traceback=traceback.format_exc(),
            )
            await workflow_context.set(
                ReservedContextKeys.EXCEPTION, exception_info, set_reserved=True
            )

            action = (
                None
                if action.on_error_action is None
                else workflow[action.on_error_action]
            )
        else:
            action = (
                None if action.next_action is None else workflow[action.next_action]
            )
        finally:
            start_from_index = 0


class PlayerManager:
    """
    Keeps track of running `action_player`s and is responsible for:
    starting, stopping and cancelling them.
    """

    def __init__(
        self,
        context: ContextInterface,
        app: FastAPI,
        workflow: Workflow,
        *,
        before_step_hook: Optional[
            Callable[[ActionName, StepName], Awaitable[None]]
        ] = None,
        after_step_hook: Optional[
            Callable[[ActionName, StepName], Awaitable[None]]
        ] = None,
    ) -> None:
        self.context = context
        self.app = app
        self.workflow = workflow
        self.before_step_hook = before_step_hook
        self.after_step_hook = after_step_hook

        self._player_tasks: dict[WorkflowName, Task] = {}
        self._workflow_context: dict[WorkflowName, WorkflowContext] = {}
        self._shutdown_tasks_workflow_context: dict[WorkflowName, Task] = {}

    async def start_action_player(
        self, play_name: WorkflowName, action_name: ActionName
    ) -> None:
        """starts a new workflow with a unique name"""

        if play_name in self._workflow_context:
            raise PlayAlreadyRunningException(play_name=play_name)
        if action_name not in self.workflow:
            raise ActionNotRegisteredException(
                action_name=action_name, workflow=self.workflow
            )

        self._workflow_context[play_name] = workflow_context = WorkflowContext(
            context=self.context,
            app=self.app,
            play_name=play_name,
            action_name=action_name,
        )
        await workflow_context.setup()

        action_player_awaitable: Awaitable = action_player(
            workflow=self.workflow,
            workflow_context=workflow_context,
            before_step_hook=self.before_step_hook,
            after_step_hook=self.after_step_hook,
        )

        self._create_action_player_task(action_player_awaitable, play_name)

    async def resume_action_player(self, workflow_context: WorkflowContext) -> None:
        # NOTE: expecting `await workflow_context.start()` to have already been ran

        action_player_awaitable: Awaitable = action_player(
            workflow=self.workflow,
            workflow_context=workflow_context,
            before_step_hook=self.before_step_hook,
            after_step_hook=self.after_step_hook,
        )

        play_name: WorkflowName = await workflow_context.get(
            ReservedContextKeys.PLAY_NAME, WorkflowName
        )
        self._create_action_player_task(action_player_awaitable, play_name)

    def _create_action_player_task(
        self, action_player_awaitable: Awaitable, play_name: WorkflowName
    ) -> None:
        play_task = self._player_tasks[play_name] = asyncio.create_task(
            action_player_awaitable, name=play_name
        )

        def action_player_complete(_: Task) -> None:
            self._player_tasks.pop(play_name, None)
            workflow_context: Optional[WorkflowContext] = self._workflow_context.pop(
                play_name, None
            )
            if workflow_context:
                # shutting down context resolver and ensure task will not be pending
                task = self._shutdown_tasks_workflow_context[
                    play_name
                ] = asyncio.create_task(workflow_context.teardown())
                task.add_done_callback(
                    partial(
                        lambda s, _: self._shutdown_tasks_workflow_context.pop(s, None),
                        play_name,
                    )
                )

        # remove when task is done
        play_task.add_done_callback(action_player_complete)

    async def wait_action_player(self, play_name: WorkflowName) -> None:
        """waits for action play task to finish"""
        if play_name not in self._player_tasks:
            raise PlayNotFoundException(workflow_name=play_name)

        player_task = self._player_tasks[play_name]
        await player_task

    @staticmethod
    async def __cancel_task(task: Optional[Task]) -> None:
        if task is None:
            return

        async def _await_task(task: Task) -> None:
            await task

        task.cancel()
        with suppress(asyncio.CancelledError):
            try:
                await asyncio.wait_for(_await_task(task), timeout=10)
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out while awaiting for cancellation of '%s'", task.get_name()
                )

    async def cancel_action_player(self, play_name: WorkflowName) -> None:
        """cancels current action player Task"""
        if play_name not in self._player_tasks:
            raise PlayNotFoundException(workflow_name=play_name)

        task = self._player_tasks[play_name]
        await self.__cancel_task(task)

    async def teardown(self) -> None:
        # NOTE: content can change while iterating
        for key in set(self._workflow_context.keys()):
            workflow_context: Optional[WorkflowContext] = self._workflow_context.get(
                key, None
            )
            if workflow_context:
                await workflow_context.teardown()

        # NOTE: content can change while iterating
        for key in set(self._shutdown_tasks_workflow_context.keys()):
            task: Optional[Task] = self._shutdown_tasks_workflow_context.get(key, None)
            await self.__cancel_task(task)

    async def setup(self) -> None:
        """currently not required"""
