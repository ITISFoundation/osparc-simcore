import asyncio
import logging
from asyncio import Task
from contextlib import suppress
from functools import partial
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI

from ._context_base import ContextInterface, ReservedContextKeys
from ._errors import (
    ActionNotRegisteredException,
    InvalidSerializedContextException,
    WorkflowAlreadyRunningException,
    WorkflowNotFoundException,
    WorkflowNotInitializedException,
)
from ._models import ActionName, StepName, WorkflowName
from ._workflow import Workflow
from ._workflow_context import WorkflowContext
from ._workflow_runner import workflow_runner

logger = logging.getLogger(__name__)


async def _cancel_task(task: Optional[Task]) -> None:
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


class WorkflowRunnerManager:
    """
    Keeps track of `workflow_runner` tasks and is responsible for:
    starting, stopping and cancelling them.
    """

    def __init__(
        self,
        context_factory: Awaitable[ContextInterface],
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
        self.context_factory = context_factory
        self.app = app
        self.workflow = workflow
        self.before_step_hook = before_step_hook
        self.after_step_hook = after_step_hook

        self._workflow_tasks: dict[WorkflowName, Task] = {}
        self._workflow_context: dict[WorkflowName, WorkflowContext] = {}
        self._workflow_context_shutdown_tasks: dict[WorkflowName, Task] = {}

    def _add_workflow_runner_task(
        self, workflow_runner_awaitable: Awaitable, workflow_name: WorkflowName
    ) -> None:
        workflow_task = self._workflow_tasks[workflow_name] = asyncio.create_task(
            workflow_runner_awaitable, name=f"workflow_task_{workflow_name}"
        )

        def workflow_runner_complete(_: Task) -> None:
            self._workflow_tasks.pop(workflow_name, None)
            workflow_context: Optional[WorkflowContext] = self._workflow_context.pop(
                workflow_name, None
            )
            if workflow_context:
                # shutting down context resolver and ensure task will not be pending
                task = self._workflow_context_shutdown_tasks[
                    workflow_name
                ] = asyncio.create_task(workflow_context.teardown())
                task.add_done_callback(
                    partial(
                        lambda s, _: self._workflow_context_shutdown_tasks.pop(s, None),
                        workflow_name,
                    )
                )

        # remove when task is done
        workflow_task.add_done_callback(workflow_runner_complete)

    async def initialize_workflow_runner(
        self, workflow_name: WorkflowName, action_name: ActionName
    ) -> None:
        """initializes a new workflow with a unique name"""

        if workflow_name in self._workflow_context:
            raise WorkflowAlreadyRunningException(workflow_name=workflow_name)
        if action_name not in self.workflow:
            raise ActionNotRegisteredException(
                action_name=action_name, workflow=self.workflow
            )

        self._workflow_context[workflow_name] = workflow_context = WorkflowContext(
            context=await self.context_factory(),
            app=self.app,
            workflow_name=workflow_name,
            action_name=action_name,
        )
        await workflow_context.setup()

    def get_workflow_context(self, workflow_name: WorkflowName) -> WorkflowContext:
        if workflow_name not in self._workflow_context:
            raise WorkflowNotInitializedException(workflow_name=workflow_name)

        return self._workflow_context[workflow_name]

    async def start_workflow_runner(self, workflow_name: WorkflowName) -> None:
        """starts an initialized workflow"""
        if workflow_name not in self._workflow_context:
            raise WorkflowNotInitializedException(workflow_name=workflow_name)

        workflow_runner_awaitable: Awaitable = workflow_runner(
            workflow=self.workflow,
            workflow_context=self._workflow_context[workflow_name],
            before_step_hook=self.before_step_hook,
            after_step_hook=self.after_step_hook,
        )

        self._add_workflow_runner_task(workflow_runner_awaitable, workflow_name)

    async def resume_workflow_runner(
        self, workflow_name: WorkflowName, serialized_context: dict[str, Any]
    ) -> None:
        if workflow_name not in self._workflow_context:
            raise WorkflowNotInitializedException(workflow_name=workflow_name)
        if (
            ReservedContextKeys.WORKFLOW_NAME not in serialized_context
            and ReservedContextKeys.WORKFLOW_ACTION_NAME not in serialized_context
            and serialized_context[ReservedContextKeys.WORKFLOW_NAME] != workflow_name
        ):
            raise InvalidSerializedContextException(
                workflow_name=workflow_name, serialized_context=serialized_context
            )

        await self._workflow_context[workflow_name].import_from_serialized_context(
            serialized_context
        )
        await self.start_workflow_runner(workflow_name)

    async def wait_workflow_runner(self, workflow_name: WorkflowName) -> None:
        """waits for action workflow task to finish"""
        if workflow_name not in self._workflow_tasks:
            raise WorkflowNotFoundException(workflow_name=workflow_name)

        workflow_task = self._workflow_tasks[workflow_name]
        await workflow_task

    async def cancel_and_wait_workflow_runner(
        self, workflow_name: WorkflowName
    ) -> None:
        """cancels current action workflow Task"""
        if workflow_name not in self._workflow_tasks:
            raise WorkflowNotFoundException(workflow_name=workflow_name)

        task = self._workflow_tasks[workflow_name]
        await _cancel_task(task)

    async def teardown(self) -> None:
        # NOTE: content can change while iterating
        for key in set(self._workflow_context.keys()):
            workflow_context: Optional[WorkflowContext] = self._workflow_context.get(
                key, None
            )
            if workflow_context:
                await workflow_context.teardown()

        # NOTE: content can change while iterating
        for key in set(self._workflow_context_shutdown_tasks.keys()):
            task: Optional[Task] = self._workflow_context_shutdown_tasks.get(key, None)
            await _cancel_task(task)

    async def setup(self) -> None:
        """no code required"""
