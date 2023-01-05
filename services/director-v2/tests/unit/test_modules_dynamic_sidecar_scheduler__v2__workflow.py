# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from pytest import LogCaptureFixture
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._context_base import (
    ContextIOInterface,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    WorkflowNotFoundException,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._marker import (
    mark_event,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._models import (
    EventName,
    StateName,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._state import (
    State,
    StateRegistry,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow import (
    ExceptionInfo,
    WorkflowManager,
    _get_event_and_index,
    workflow_runner,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._workflow_context_resolver import (
    WorkflowContextResolver,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _workflow_manager_lifecycle(workflow_manager: WorkflowManager) -> None:
    try:
        await workflow_manager.start()
        yield None
    finally:
        await workflow_manager.shutdown()


async def test_iter_from():
    async def first():
        pass

    async def second():
        pass

    async def third():
        pass

    awaitables = [first, second, third]
    event_sequence = list(enumerate(awaitables))

    three_element_list = list(_get_event_and_index(awaitables))
    assert three_element_list == event_sequence
    assert len(three_element_list) == 3

    three_element_list = list(_get_event_and_index(awaitables, index=0))
    assert three_element_list == event_sequence
    assert len(three_element_list) == 3

    two_element_list = list(_get_event_and_index(awaitables, index=1))
    assert two_element_list == event_sequence[1:]
    assert len(two_element_list) == 2

    one_element_list = list(_get_event_and_index(awaitables, index=2))
    assert one_element_list == event_sequence[2:]
    assert len(one_element_list) == 1

    for out_of_bound_index in range(3, 10):
        zero_element_list = list(
            _get_event_and_index(awaitables, index=out_of_bound_index)
        )
        assert zero_element_list == event_sequence[out_of_bound_index:]
        assert len(zero_element_list) == 0


async def test_workflow_runner(
    storage_context: ContextIOInterface, caplog_info_level: LogCaptureFixture
):
    context_resolver = WorkflowContextResolver(
        storage_context, app=FastAPI(), workflow_name="unique", state_name="first"
    )
    await context_resolver.start()

    # define some states
    # then run them to see how it works

    @mark_event
    async def initial_state() -> dict[str, Any]:
        print("initial state")
        return {"x": 10, "y": 12.3}

    @mark_event
    async def verify(x: int, y: float) -> dict[str, Any]:
        assert type(x) == int
        assert type(y) == float
        return {"z": x + y}

    @mark_event
    async def print_second() -> dict[str, Any]:
        print("SECOND")
        return {}

    FIRST_STATE = State(
        name="first",
        events=[
            initial_state,
            verify,
        ],
        next_state="second",
        on_error_state=None,
    )
    SECOND_STATE = State(
        name="second",
        events=[
            print_second,
            verify,
            verify,
        ],
        next_state=None,
        on_error_state=None,
    )

    state_registry = StateRegistry(FIRST_STATE, SECOND_STATE)

    async def hook_before(state: StateName, event: EventName) -> None:
        logger.info("hook_before %s %s", f"{state=}", f"{event=}")

    async def hook_after(state: StateName, event: EventName) -> None:
        logger.info("hook_after %s %s", f"{state=}", f"{event=}")

    await workflow_runner(
        state_registry=state_registry,
        context_resolver=context_resolver,
        before_event_hook=hook_before,
        after_event_hook=hook_after,
    )

    # check hooks are working as expected
    assert (
        "hook_before state='first' event='initial_state'" in caplog_info_level.messages
    )
    assert (
        "hook_after state='first' event='initial_state'" in caplog_info_level.messages
    )

    await context_resolver.shutdown()


async def test_workflow_manager(storage_context: ContextIOInterface):
    @mark_event
    async def initial_state() -> dict[str, Any]:
        print("initial state")
        return {"x": 10, "y": 12.3}

    @mark_event
    async def verify(x: int, y: float) -> dict[str, Any]:
        assert type(x) == int
        assert type(y) == float
        return {"z": x + y}

    @mark_event
    async def print_second() -> dict[str, Any]:
        print("SECOND")
        return {}

    FIRST_STATE = State(
        name="first",
        events=[
            initial_state,
            verify,
        ],
        next_state="second",
        on_error_state=None,
    )
    SECOND_STATE = State(
        name="second",
        events=[
            print_second,
            verify,
            verify,
        ],
        next_state=None,
        on_error_state=None,
    )

    state_registry = StateRegistry(FIRST_STATE, SECOND_STATE)

    workflow_manager = WorkflowManager(
        storage_context=storage_context, app=FastAPI(), state_registry=state_registry
    )
    async with _workflow_manager_lifecycle(workflow_manager):
        # ok workflow
        await workflow_manager.run_workflow(
            workflow_name="start_first", state_name="first"
        )
        assert "start_first" in workflow_manager._workflow_context
        assert "start_first" in workflow_manager._workflow_tasks
        await workflow_manager.wait_workflow("start_first")
        assert "start_first" not in workflow_manager._workflow_context
        assert "start_first" not in workflow_manager._workflow_tasks

        # cancel workflow
        await workflow_manager.run_workflow(
            workflow_name="start_first", state_name="first"
        )
        await workflow_manager.cancel_workflow("start_first")
        assert "start_first" not in workflow_manager._workflow_context
        assert "start_first" not in workflow_manager._workflow_tasks
        with pytest.raises(WorkflowNotFoundException):
            await workflow_manager.wait_workflow("start_first")


async def test_workflow_manager_error_handling(
    storage_context: ContextIOInterface,
):
    ERROR_MARKER_IN_TB = "__this message must be present in the traceback__"

    @mark_event
    async def error_raiser() -> dict[str, Any]:
        raise RuntimeError(ERROR_MARKER_IN_TB)

    @mark_event
    async def graceful_error_handler(_exception: ExceptionInfo) -> dict[str, Any]:
        assert _exception.exception_class == RuntimeError
        assert _exception.state_name in {"case_1_rasing_error", "case_2_rasing_error"}
        assert _exception.event_name == error_raiser.__name__
        assert ERROR_MARKER_IN_TB in _exception.serialized_traceback
        await asyncio.sleep(0.1)
        return {}

    # CASE 1
    # error is raised by first state, second state handles it -> no error raised
    CASE_1_RAISING_ERROR = State(
        name="case_1_rasing_error",
        events=[
            error_raiser,
        ],
        next_state=None,
        on_error_state="case_1_handling_error",
    )
    CASE_1_HANDLING_ERROR = State(
        name="case_1_handling_error",
        events=[
            graceful_error_handler,
        ],
        next_state=None,
        on_error_state=None,
    )

    # CASE 2
    # error is raised by first state -> raises error
    CASE_2_RASING_ERROR = State(
        name="case_2_raising_error",
        events=[
            error_raiser,
        ],
        next_state=None,
        on_error_state=None,
    )

    state_registry = StateRegistry(
        CASE_1_RAISING_ERROR,
        CASE_1_HANDLING_ERROR,
        CASE_2_RASING_ERROR,
    )

    workflow_name = "test_workflow"
    # CASE 1
    workflow_manager = WorkflowManager(
        storage_context=storage_context, app=FastAPI(), state_registry=state_registry
    )
    async with _workflow_manager_lifecycle(workflow_manager):
        await workflow_manager.run_workflow(
            workflow_name=workflow_name, state_name="case_1_rasing_error"
        )
        await workflow_manager.wait_workflow(workflow_name)

    # CASE 2
    workflow_manager = WorkflowManager(
        storage_context=storage_context, app=FastAPI(), state_registry=state_registry
    )
    async with _workflow_manager_lifecycle(workflow_manager):
        await workflow_manager.run_workflow(
            workflow_name=workflow_name, state_name="case_2_raising_error"
        )
        with pytest.raises(RuntimeError):
            await workflow_manager.wait_workflow(workflow_name)
