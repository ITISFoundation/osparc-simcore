# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterable, Awaitable
from unittest.mock import AsyncMock, call

import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._action import (
    Action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._context_base import (
    ContextInterface,
    ReservedContextKeys,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._errors import (
    ActionNotRegisteredException,
    InvalidSerializedContextException,
    WorkflowAlreadyExistingException,
    WorkflowNotFoundException,
    WorkflowNotInitializedException,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._marker import (
    mark_step,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._models import (
    ExceptionInfo,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._workflow import (
    Workflow,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._workflow_context import (
    WorkflowContext,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._workflow_runner_manager import (
    WorkflowRunnerManager,
)

# UTILS


@asynccontextmanager
async def _workflow_runner_manager_lifecycle(
    workflow_runner_manager: WorkflowRunnerManager,
) -> None:
    try:
        await workflow_runner_manager.setup()
        yield None
    finally:
        await workflow_runner_manager.teardown()


# FIXTURES


@pytest.fixture
async def simple_workflow_runner_manager(
    context_interface_factory: Awaitable[ContextInterface],
) -> AsyncIterable[WorkflowRunnerManager]:
    workflow = Workflow(
        Action(name="", steps=[], next_action=None, on_error_action=None)
    )
    workflow_runner_manager = WorkflowRunnerManager(
        context_factory=context_interface_factory, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(workflow_runner_manager):
        yield workflow_runner_manager


# TESTS


async def test_initialize_workflow_runner_exceptions(
    simple_workflow_runner_manager: WorkflowRunnerManager,
):
    await simple_workflow_runner_manager.initialize_workflow_runner(
        workflow_name="first", action_name=""
    )
    with pytest.raises(WorkflowAlreadyExistingException):
        await simple_workflow_runner_manager.initialize_workflow_runner(
            workflow_name="first", action_name=""
        )

    with pytest.raises(ActionNotRegisteredException):
        await simple_workflow_runner_manager.initialize_workflow_runner(
            workflow_name="second", action_name="not_registered"
        )


async def test_get_workflow_context_exception(
    simple_workflow_runner_manager: WorkflowRunnerManager,
):
    with pytest.raises(WorkflowNotInitializedException):
        simple_workflow_runner_manager.get_workflow_context("not_existing_workflow")


async def test_start_workflow_runner_exception(
    simple_workflow_runner_manager: WorkflowRunnerManager,
):
    with pytest.raises(WorkflowNotInitializedException):
        await simple_workflow_runner_manager.start_workflow_runner("first")


async def test_resume_workflow_runner_exceptions(
    simple_workflow_runner_manager: WorkflowRunnerManager,
):
    invalid_serialized_context = {}

    with pytest.raises(WorkflowNotInitializedException):
        await simple_workflow_runner_manager.resume_workflow_runner(
            "first", invalid_serialized_context
        )

    await simple_workflow_runner_manager.initialize_workflow_runner(
        workflow_name="first", action_name=""
    )
    with pytest.raises(InvalidSerializedContextException):
        await simple_workflow_runner_manager.resume_workflow_runner(
            "first", invalid_serialized_context
        )


async def test_wait_workflow_runner_exception(
    simple_workflow_runner_manager: WorkflowRunnerManager,
):
    with pytest.raises(WorkflowNotFoundException):
        await simple_workflow_runner_manager.wait_workflow_runner(
            "not_started_workflow"
        )


async def test_cancel_and_wait_workflow_runner_exception(
    simple_workflow_runner_manager: WorkflowRunnerManager,
):
    with pytest.raises(WorkflowNotFoundException):
        await simple_workflow_runner_manager.cancel_and_wait_workflow_runner(
            "not_started_workflow"
        )


async def test_workflow_runner_manager(
    context_interface_factory: Awaitable[ContextInterface],
):
    @mark_step
    async def initial_state() -> dict[str, Any]:
        print("initial state")
        return {"x": 10, "y": 12.3}

    @mark_step
    async def verify(x: int, y: float) -> dict[str, Any]:
        assert type(x) == int
        assert type(y) == float
        return {"z": x + y}

    @mark_step
    async def print_second() -> dict[str, Any]:
        print("SECOND")
        return {}

    FIRST_ACTION = Action(
        name="first",
        steps=[
            initial_state,
            verify,
        ],
        next_action="second",
        on_error_action=None,
    )
    SECOND_ACTION = Action(
        name="second",
        steps=[
            print_second,
            verify,
            verify,
        ],
        next_action=None,
        on_error_action=None,
    )

    workflow = Workflow(FIRST_ACTION, SECOND_ACTION)

    workflow_runner_manager = WorkflowRunnerManager(
        context_factory=context_interface_factory, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(workflow_runner_manager):
        # ok workflow_runner
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name="start_first", action_name="first"
        )
        await workflow_runner_manager.start_workflow_runner(workflow_name="start_first")
        assert "start_first" in workflow_runner_manager._workflow_context
        assert "start_first" in workflow_runner_manager._workflow_tasks
        await workflow_runner_manager.wait_workflow_runner("start_first")
        assert "start_first" not in workflow_runner_manager._workflow_context
        assert "start_first" not in workflow_runner_manager._workflow_tasks

        # cancel workflow_runner
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name="start_first", action_name="first"
        )
        await workflow_runner_manager.start_workflow_runner(workflow_name="start_first")
        await workflow_runner_manager.cancel_and_wait_workflow_runner("start_first")
        assert "start_first" not in workflow_runner_manager._workflow_context
        assert "start_first" not in workflow_runner_manager._workflow_tasks
        with pytest.raises(WorkflowNotFoundException):
            await workflow_runner_manager.wait_workflow_runner("start_first")


async def test_workflow_runner_error_handling(
    context_interface_factory: Awaitable[ContextInterface],
):
    ERROR_MARKER_IN_TB = "__this message must be present in the traceback__"

    @mark_step
    async def error_raiser() -> dict[str, Any]:
        raise RuntimeError(ERROR_MARKER_IN_TB)

    @mark_step
    async def graceful_error_handler(
        unexpected_runtime_exception: ExceptionInfo,
    ) -> dict[str, Any]:
        assert unexpected_runtime_exception.exception_class == RuntimeError
        assert unexpected_runtime_exception.action_name in {
            "case_1_rasing_error",
            "case_2_rasing_error",
        }
        assert unexpected_runtime_exception.step_name == error_raiser.__name__
        assert ERROR_MARKER_IN_TB in unexpected_runtime_exception.serialized_traceback
        await asyncio.sleep(0.1)
        return {}

    # CASE 1
    # error is raised by first state, second state handles it -> no error raised
    CASE_1_RAISING_ERROR = Action(
        name="case_1_rasing_error",
        steps=[
            error_raiser,
        ],
        next_action=None,
        on_error_action="case_1_handling_error",
    )
    CASE_1_HANDLING_ERROR = Action(
        name="case_1_handling_error",
        steps=[
            graceful_error_handler,
        ],
        next_action=None,
        on_error_action=None,
    )

    # CASE 2
    # error is raised by first state -> raises error
    CASE_2_RASING_ERROR = Action(
        name="case_2_raising_error",
        steps=[
            error_raiser,
        ],
        next_action=None,
        on_error_action=None,
    )

    workflow = Workflow(
        CASE_1_RAISING_ERROR,
        CASE_1_HANDLING_ERROR,
        CASE_2_RASING_ERROR,
    )

    workflow_name = "test_workflow_name"
    # CASE 1
    workflow_runner_manager = WorkflowRunnerManager(
        context_factory=context_interface_factory, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(workflow_runner_manager):
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name=workflow_name, action_name="case_1_rasing_error"
        )
        await workflow_runner_manager.start_workflow_runner(workflow_name=workflow_name)
        await workflow_runner_manager.wait_workflow_runner(workflow_name)

    # CASE 2
    workflow_runner_manager = WorkflowRunnerManager(
        context_factory=context_interface_factory, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(workflow_runner_manager):
        await workflow_runner_manager.initialize_workflow_runner(
            workflow_name=workflow_name, action_name="case_2_raising_error"
        )
        await workflow_runner_manager.start_workflow_runner(workflow_name=workflow_name)
        with pytest.raises(RuntimeError):
            await workflow_runner_manager.wait_workflow_runner(workflow_name)


async def test_resume_workflow_runner_workflow(
    context_interface_factory: Awaitable[ContextInterface],
):
    call_tracker_1 = AsyncMock()
    call_tracker_2 = AsyncMock()

    @mark_step
    async def first_step() -> dict[str, Any]:
        await call_tracker_1(first_step)
        return {}

    @mark_step
    async def optionally_long_sleep(sleep: bool) -> dict[str, Any]:
        if sleep:
            await call_tracker_1(optionally_long_sleep)
            await asyncio.sleep(1e10)
        await call_tracker_2(optionally_long_sleep)
        return {}

    @mark_step
    async def third_step() -> dict[str, Any]:
        await call_tracker_2(third_step)
        return {}

    workflow = Workflow(
        Action(
            name="initial",
            steps=[
                first_step,
                optionally_long_sleep,
                third_step,
            ],
            next_action=None,
            on_error_action=None,
        )
    )

    # start workflow which will wait forever on step `optionally_long_sleep`
    first_workflow_runner_manager = WorkflowRunnerManager(
        context_factory=context_interface_factory, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(first_workflow_runner_manager):
        await first_workflow_runner_manager.initialize_workflow_runner(
            "test", action_name="initial"
        )

        # NOTE: allows the workflow to wait for forever
        # this is also a way to initialize some data before
        # starting the workflow_runner
        # NOTE: after calling `cancel_and_wait_workflow_runner`, `WorkflowRunnerManager`
        # will no longer keep track of the context of the workflow
        first_context: WorkflowContext = (
            first_workflow_runner_manager.get_workflow_context("test")
        )
        await first_context.set("sleep", True)
        await first_workflow_runner_manager.start_workflow_runner("test")

        WAIT_TO_REACH_SECOND_STEP = 0.1
        await asyncio.sleep(WAIT_TO_REACH_SECOND_STEP)
        await first_workflow_runner_manager.cancel_and_wait_workflow_runner("test")

    # ensure state as expected, stopped while handling `optionally_long_sleep``
    assert call_tracker_1.call_args_list == [
        call(first_step),
        call(optionally_long_sleep),
    ]
    serialized_first_context_data = await first_context.get_serialized_context()
    assert serialized_first_context_data == {
        "sleep": True,
        ReservedContextKeys.WORKFLOW_ACTION_NAME: "initial",
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_INDEX: 1,
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_NAME: "optionally_long_sleep",
        ReservedContextKeys.WORKFLOW_NAME: "test",
    }

    # resume workflow which rune from step `optionally_long_sleep` and finish

    second_workflow_runner_manager = WorkflowRunnerManager(
        context_factory=context_interface_factory, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(second_workflow_runner_manager):
        await second_workflow_runner_manager.initialize_workflow_runner(
            "test", action_name="initial"
        )
        # NOTE: after calling `wait_workflow_runner`, `WorkflowRunnerManager`
        # will no longer keep track of the context of the workflow
        second_context: WorkflowContext = (
            second_workflow_runner_manager.get_workflow_context("test")
        )

        # NOTE: allows the workflow to finish, normally the incoming
        # serialized_context would not be touched,
        # this is just required for the test
        serialized_first_context_data["sleep"] = False

        workflow_name = serialized_first_context_data[ReservedContextKeys.WORKFLOW_NAME]
        await second_workflow_runner_manager.resume_workflow_runner(
            workflow_name=workflow_name,
            serialized_context=serialized_first_context_data,
        )
        await second_workflow_runner_manager.wait_workflow_runner(workflow_name)

    # ensure state as expected, finished on `third_step`
    assert call_tracker_2.call_args_list == [
        call(optionally_long_sleep),
        call(third_step),
    ]
    new_context_data = await second_context.get_serialized_context()
    assert new_context_data == {
        "sleep": False,
        ReservedContextKeys.WORKFLOW_ACTION_NAME: "initial",
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_INDEX: 2,
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_NAME: "third_step",
        ReservedContextKeys.WORKFLOW_NAME: "test",
    }
