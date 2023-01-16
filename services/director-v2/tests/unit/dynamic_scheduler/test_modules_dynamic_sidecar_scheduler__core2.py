# pylint: disable=redefined-outer-name

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable
from unittest.mock import AsyncMock, call

import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2 import (
    Action,
    ExceptionInfo,
    Workflow,
    WorkflowRunnerManager,
    mark_step,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._context_base import (
    ContextInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._models import (
    WorkflowName,
)

logger = logging.getLogger(__name__)


# UTILS


@asynccontextmanager
async def workflow_runner_manager_lifecycle(
    app: AsyncMock,
    context_interface_factory: Awaitable[ContextInterface],
    workflow: Workflow,
) -> AsyncIterator[WorkflowRunnerManager]:
    workflow_runner_manager = WorkflowRunnerManager(
        context_factory=context_interface_factory, app=app, workflow=workflow
    )
    await workflow_runner_manager.setup()
    yield workflow_runner_manager
    await workflow_runner_manager.teardown()


# FIXTURES


@pytest.fixture
def app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def workflow_name() -> WorkflowName:
    return "test_workflow_name"


# TESTS


async def test_workflow_runs_in_expected_order_without_errors(
    app: AsyncMock,
    context_interface_factory: Awaitable[ContextInterface],
    workflow_name: WorkflowName,
):
    call_tracker = AsyncMock()

    @mark_step
    async def initialize_workflow() -> dict[str, Any]:
        await call_tracker(initialize_workflow)
        return {"number_a": 10, "number_b": 2}

    @mark_step
    async def compute_product(number_a: int, number_b: int) -> dict[str, Any]:
        await call_tracker(compute_product)
        product = number_a * number_b
        return {"product": product}

    @mark_step
    async def check_result(product: int) -> dict[str, Any]:
        await call_tracker(check_result)
        assert product == 20
        return {}

    workflow = Workflow(
        Action(
            name="initialize",
            steps=[
                initialize_workflow,
            ],
            next_action="compute",
            on_error_action=None,
        ),
        Action(
            name="compute",
            steps=[
                compute_product,
            ],
            next_action="validate",
            on_error_action=None,
        ),
        Action(
            name="validate",
            steps=[
                check_result,
            ],
            next_action=None,
            on_error_action=None,
        ),
    )

    async with workflow_runner_manager_lifecycle(
        app, context_interface_factory, workflow
    ) as workflow_runner_manager:

        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name=workflow_name, action_name="initialize"
        )
        await workflow_runner_manager.start_workflow_runner(workflow_name=workflow_name)
        await workflow_runner_manager.wait_workflow_runner(workflow_name)

        assert call_tracker.call_args_list == [
            call(initialize_workflow),
            call(compute_product),
            call(check_result),
        ]


async def test_error_raised_but_handled_by_on_error_action(
    app: AsyncMock,
    context_interface_factory: Awaitable[ContextInterface],
    workflow_name: WorkflowName,
):
    call_tracker = AsyncMock()

    class HandledError(RuntimeError):
        ...

    @mark_step
    async def error_raising() -> dict[str, Any]:
        await call_tracker(error_raising)
        raise HandledError()

    @mark_step
    async def handle_error(
        unexpected_runtime_exception: ExceptionInfo,
    ) -> dict[str, Any]:
        await call_tracker(handle_error)
        # NOTE: the users has a chance to do something here based on the
        # generated exception
        print("Raised exception data", unexpected_runtime_exception)
        return {}

    workflow = Workflow(
        Action(
            name="raising_error",
            steps=[error_raising],
            next_action=None,
            on_error_action="error_handling",
        ),
        Action(
            name="error_handling",
            steps=[handle_error],
            next_action=None,
            on_error_action=None,
        ),
    )
    async with workflow_runner_manager_lifecycle(
        app, context_interface_factory, workflow
    ) as workflow_runner_manager:
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name=workflow_name, action_name="raising_error"
        )
        await workflow_runner_manager.start_workflow_runner(workflow_name=workflow_name)
        await workflow_runner_manager.wait_workflow_runner(workflow_name)

        assert call_tracker.call_args_list == [
            call(error_raising),
            call(handle_error),
        ]


async def test_error_raised_but_not_handled(
    app: AsyncMock,
    context_interface_factory: Awaitable[ContextInterface],
    workflow_name: WorkflowName,
):
    call_tracker = AsyncMock()

    class UnhandledError(RuntimeError):
        ...

    @mark_step
    async def error_raising() -> dict[str, Any]:
        await call_tracker(error_raising)
        raise UnhandledError()

    workflow = Workflow(
        Action(
            name="raising_error",
            steps=[error_raising],
            next_action=None,
            on_error_action=None,
        )
    )
    async with workflow_runner_manager_lifecycle(
        app, context_interface_factory, workflow
    ) as workflow_runner_manager:
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name=workflow_name, action_name="raising_error"
        )
        await workflow_runner_manager.start_workflow_runner(workflow_name=workflow_name)
        with pytest.raises(UnhandledError):
            await workflow_runner_manager.wait_workflow_runner(workflow_name)

        assert call_tracker.call_args_list == [
            call(error_raising),
        ]


# TEST 4: test cancellation of very long pending event and schedule a new workflow which will finish
async def test_cancellation_of_current_workflow_and_changing_to_a_different_one(
    app: AsyncMock, context_interface_factory: Awaitable[ContextInterface]
):
    call_tracker = AsyncMock()

    # WORKFLOW_PENDING_FOREVER

    @mark_step
    async def pending_forever() -> dict[str, Any]:
        await call_tracker(pending_forever)
        await asyncio.sleep(1e10)
        return {}

    workflow_pending = Workflow(
        Action(
            name="pending",
            steps=[pending_forever],
            next_action=None,
            on_error_action=None,
        )
    )

    # WORKFLOW_FINISHES_IMMEDIATELY

    @mark_step
    async def print_something_and_finish() -> dict[str, Any]:
        await call_tracker(print_something_and_finish)
        print("a thing")
        return {}

    workflow_finishing = Workflow(
        Action(
            name="finishing",
            steps=[print_something_and_finish],
            next_action=None,
            on_error_action=None,
        )
    )

    async with workflow_runner_manager_lifecycle(
        app=app,
        context_interface_factory=context_interface_factory,
        workflow=workflow_pending + workflow_finishing,
    ) as workflow_runner_manager:

        # start the first workflow and cancel it immediately
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name="pending_workflow", action_name="pending"
        )
        await workflow_runner_manager.start_workflow_runner(
            workflow_name="pending_workflow"
        )
        WAIT_FOR_STEP_TO_START = 0.1
        await asyncio.sleep(WAIT_FOR_STEP_TO_START)
        await workflow_runner_manager.cancel_and_wait_workflow_runner(
            "pending_workflow"
        )

        # start second workflow which wil finish afterwards
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name="finishing_workflow", action_name="finishing"
        )
        await workflow_runner_manager.start_workflow_runner(
            workflow_name="finishing_workflow"
        )
        await workflow_runner_manager.wait_workflow_runner("finishing_workflow")

        assert call_tracker.call_args_list == [
            call(pending_forever),
            call(print_something_and_finish),
        ]
