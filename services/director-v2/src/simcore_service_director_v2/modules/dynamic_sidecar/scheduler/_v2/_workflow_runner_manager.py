import asyncio
import logging
from asyncio import Task
from contextlib import suppress
from functools import partial
from typing import Awaitable, Callable, Optional

from fastapi import FastAPI

from ._context_base import ContextInterface, ReservedContextKeys
from ._errors import (
    ActionNotRegisteredException,
    PlayAlreadyRunningException,
    PlayNotFoundException,
)
from ._models import ActionName, StepName, WorkflowName
from ._workflow import Workflow
from ._workflow_context import WorkflowContext
from ._workflow_runner import workflow_runner

logger = logging.getLogger(__name__)


class WorkflowRunnerManager:
    """
    Keeps track of running `workflow_runner`s and is responsible for:
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

    async def start_workflow_runner(
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

        workflow_runner_awaitable: Awaitable = workflow_runner(
            workflow=self.workflow,
            workflow_context=workflow_context,
            before_step_hook=self.before_step_hook,
            after_step_hook=self.after_step_hook,
        )

        self._create_workflow_runner_task(workflow_runner_awaitable, play_name)

    async def resume_workflow_runner(self, workflow_context: WorkflowContext) -> None:
        # NOTE: expecting `await workflow_context.start()` to have already been ran

        workflow_runner_awaitable: Awaitable = workflow_runner(
            workflow=self.workflow,
            workflow_context=workflow_context,
            before_step_hook=self.before_step_hook,
            after_step_hook=self.after_step_hook,
        )

        play_name: WorkflowName = await workflow_context.get(
            ReservedContextKeys.PLAY_NAME, WorkflowName
        )
        self._create_workflow_runner_task(workflow_runner_awaitable, play_name)

    def _create_workflow_runner_task(
        self, workflow_runner_awaitable: Awaitable, play_name: WorkflowName
    ) -> None:
        play_task = self._player_tasks[play_name] = asyncio.create_task(
            workflow_runner_awaitable, name=play_name
        )

        def workflow_runner_complete(_: Task) -> None:
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
        play_task.add_done_callback(workflow_runner_complete)

    async def wait_workflow_runner(self, play_name: WorkflowName) -> None:
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

    async def cancel_and_wait_workflow_runner(self, play_name: WorkflowName) -> None:
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
