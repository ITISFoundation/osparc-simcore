# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, call

import pytest
from pytest import LogCaptureFixture
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._action import (
    Action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextInterface,
    ReservedContextKeys,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    WorkflowNotFoundException,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._marker import (
    mark_step,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._models import (
    ActionName,
    StepName,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow import (
    Workflow,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow_context import (
    WorkflowContext,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow_runner import (
    ExceptionInfo,
    _iter_index_step,
    workflow_runner,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow_runner_manager import (
    WorkflowRunnerManager,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _workflow_runner_manager_lifecycle(
    workflow_runner_manager: WorkflowRunnerManager,
) -> None:
    try:
        await workflow_runner_manager.setup()
        yield None
    finally:
        await workflow_runner_manager.teardown()


async def test_iter_index_step():
    async def first():
        pass

    async def second():
        pass

    async def third():
        pass

    awaitables = [first, second, third]
    step_sequence = list(enumerate(awaitables))

    three_element_list = list(_iter_index_step(awaitables))
    assert three_element_list == step_sequence
    assert len(three_element_list) == 3

    three_element_list = list(_iter_index_step(awaitables, index=0))
    assert three_element_list == step_sequence
    assert len(three_element_list) == 3

    two_element_list = list(_iter_index_step(awaitables, index=1))
    assert two_element_list == step_sequence[1:]
    assert len(two_element_list) == 2

    one_element_list = list(_iter_index_step(awaitables, index=2))
    assert one_element_list == step_sequence[2:]
    assert len(one_element_list) == 1

    for out_of_bound_index in range(3, 10):
        zero_element_list = list(_iter_index_step(awaitables, index=out_of_bound_index))
        assert zero_element_list == step_sequence[out_of_bound_index:]
        assert len(zero_element_list) == 0


@pytest.fixture
async def workflow_context(
    context: ContextInterface,
) -> WorkflowContext:
    workflow_context = WorkflowContext(
        context=context, app=AsyncMock(), workflow_name="unique", action_name="first"
    )
    await workflow_context.setup()
    yield workflow_context
    await workflow_context.teardown()


async def test_workflow_runner(
    workflow_context: WorkflowContext, caplog_info_level: LogCaptureFixture
):
    @mark_step
    async def initial() -> dict[str, Any]:
        print("initial")
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

    FIRST_STATE = Action(
        name="first",
        steps=[
            initial,
            verify,
        ],
        next_action="second",
        on_error_action=None,
    )
    SECOND_STATE = Action(
        name="second",
        steps=[
            print_second,
            verify,
            verify,
        ],
        next_action=None,
        on_error_action=None,
    )

    workflow = Workflow(FIRST_STATE, SECOND_STATE)

    async def hook_before(action: ActionName, step: StepName) -> None:
        logger.info("hook_before %s %s", f"{action=}", f"{step=}")

    async def hook_after(action: ActionName, step: StepName) -> None:
        logger.info("hook_after %s %s", f"{action=}", f"{step=}")

    await workflow_runner(
        workflow=workflow,
        workflow_context=workflow_context,
        before_step_hook=hook_before,
        after_step_hook=hook_after,
    )

    # check hooks are working as expected
    assert "hook_before action='first' step='initial'" in caplog_info_level.messages
    assert "hook_after action='first' step='initial'" in caplog_info_level.messages


async def test_workflow_runner_manager(context: ContextInterface):
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
        context=context, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(workflow_runner_manager):
        # ok workflow_runner
        await workflow_runner_manager.start_workflow_runner(
            workflow_name="start_first", action_name="first"
        )
        assert "start_first" in workflow_runner_manager._workflow_context
        assert "start_first" in workflow_runner_manager._workflow_tasks
        await workflow_runner_manager.wait_workflow_runner("start_first")
        assert "start_first" not in workflow_runner_manager._workflow_context
        assert "start_first" not in workflow_runner_manager._workflow_tasks

        # cancel workflow_runner
        await workflow_runner_manager.start_workflow_runner(
            workflow_name="start_first", action_name="first"
        )
        await workflow_runner_manager.cancel_and_wait_workflow_runner("start_first")
        assert "start_first" not in workflow_runner_manager._workflow_context
        assert "start_first" not in workflow_runner_manager._workflow_tasks
        with pytest.raises(WorkflowNotFoundException):
            await workflow_runner_manager.wait_workflow_runner("start_first")


async def test_workflow_runner_error_handling(
    context: ContextInterface,
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
        context=context, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(workflow_runner_manager):
        await workflow_runner_manager.start_workflow_runner(
            workflow_name=workflow_name, action_name="case_1_rasing_error"
        )
        await workflow_runner_manager.wait_workflow_runner(workflow_name)

    # CASE 2
    workflow_runner_manager = WorkflowRunnerManager(
        context=context, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(workflow_runner_manager):
        await workflow_runner_manager.start_workflow_runner(
            workflow_name=workflow_name, action_name="case_2_raising_error"
        )
        with pytest.raises(RuntimeError):
            await workflow_runner_manager.wait_workflow_runner(workflow_name)


async def test_resume_workflow_runner_workflow(
    context_io_interface_type: type[ContextInterface],
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
    first_context = context_io_interface_type()
    second_workflow_runner_manager = WorkflowRunnerManager(
        context=first_context, app=AsyncMock(), workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(second_workflow_runner_manager):
        # NOTE: allows the workflow to wait for forever
        await first_context.save("sleep", True)
        await second_workflow_runner_manager.start_workflow_runner(
            "test", action_name="initial"
        )

        WAIT_TO_REACH_SECOND_STEP = 0.1
        await asyncio.sleep(WAIT_TO_REACH_SECOND_STEP)
        await second_workflow_runner_manager.cancel_and_wait_workflow_runner("test")

    # ensure state as expected, stopped while handling `optionally_long_sleep``
    assert call_tracker_1.call_args_list == [
        call(first_step),
        call(optionally_long_sleep),
    ]
    serialized_first_context_data = await first_context.to_dict()
    assert serialized_first_context_data == {
        "sleep": True,
        ReservedContextKeys.WORKFLOW_ACTION_NAME: "initial",
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_INDEX: 1,
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_NAME: "optionally_long_sleep",
        ReservedContextKeys.WORKFLOW_NAME: "test",
    }

    # resume workflow which rune from step `optionally_long_sleep` and finish
    second_context = context_io_interface_type()
    mock_app = AsyncMock()

    second_workflow_runner_manager = WorkflowRunnerManager(
        context=second_context, app=mock_app, workflow=workflow
    )
    async with _workflow_runner_manager_lifecycle(second_workflow_runner_manager):
        # NOTE: allows the workflow to finish
        serialized_first_context_data["sleep"] = False
        await second_workflow_runner_manager.resume_workflow_runner(
            workflow_context=await WorkflowContext.from_dict(
                context=second_context,
                app=mock_app,
                incoming=serialized_first_context_data,
            )
        )

        workflow_name = await second_context.load(ReservedContextKeys.WORKFLOW_NAME)
        await second_workflow_runner_manager.wait_workflow_runner(workflow_name)

    # ensure state as expected, finished on `third_step`
    assert call_tracker_2.call_args_list == [
        call(optionally_long_sleep),
        call(third_step),
    ]
    new_context_data = await second_context.to_dict()
    assert new_context_data == {
        "sleep": False,
        ReservedContextKeys.WORKFLOW_ACTION_NAME: "initial",
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_INDEX: 2,
        ReservedContextKeys.WORKFLOW_CURRENT_STEP_NAME: "third_step",
        ReservedContextKeys.WORKFLOW_NAME: "test",
    }
