# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest import LogCaptureFixture
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._action import (
    Action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._context_base import (
    ContextInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._marker import (
    mark_step,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._models import (
    ActionName,
    StepName,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._workflow import (
    Workflow,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._workflow_context import (
    WorkflowContext,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._workflow_runner import (
    _iter_index_step,
    workflow_runner,
)

logger = logging.getLogger(__name__)


# FIXTURES


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


# TESTS


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


# TESTS


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
