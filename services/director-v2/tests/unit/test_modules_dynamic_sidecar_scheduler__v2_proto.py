# pylint: disable=protected-access

import asyncio
from typing import Any

import pytest
from fastapi import FastAPI
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._proto import (
    ContextResolver,
    ExceptionInfo,
    NotAllowedContextKeyError,
    ReservedContextKeys,
    State,
    StateRegistry,
    WorkflowManager,
    WorkflowNotFoundException,
    _get_event_and_index,
    mark_event,
    workflow_runner,
)


async def test_register_event_with_return_value():
    @mark_event
    async def return_inputs(x: str, y: float, z: dict[str, int]) -> dict[str, Any]:
        return {"x": x, "y": y, "z": z}

    assert return_inputs.input_types == {"x": str, "y": float, "z": dict[str, int]}

    assert await return_inputs(1, 2, {"ciao": 3}) == dict(x=1, y=2, z={"ciao": 3})


# TODO: test with wrong return type!
# TODO: test to see for state definition
# TODO: test to ensure the chained serializers for events I/O chains are working


async def test_state_definition_ok():
    @mark_event
    async def print_info() -> dict[str, Any]:
        print("some info")
        return {}

    @mark_event
    async def verify(x: float, y: int) -> dict[str, Any]:
        assert type(x) == float
        assert type(y) == int
        return {}

    INFO_CHECK = State(
        name="test",
        events=[
            print_info,
            verify,
        ],
        next_state=None,
        on_error_state=None,
    )
    assert INFO_CHECK


def test_state_registry():
    STATE_ONE_NAME = "one"
    STATE_TWO_NAME = "two"
    STATE_MISSING_NAME = "not_existing_state"

    state_one = State(
        name=STATE_ONE_NAME, events=[], next_state=None, on_error_state=None
    )
    state_two = State(
        name=STATE_TWO_NAME, events=[], next_state=None, on_error_state=None
    )

    registry = StateRegistry(
        state_one,
        state_two,
    )

    # in operator
    assert STATE_ONE_NAME in registry
    assert STATE_TWO_NAME in registry
    assert STATE_MISSING_NAME not in registry

    # get key operator
    assert registry[STATE_ONE_NAME] == state_one
    assert registry[STATE_TWO_NAME] == state_two
    with pytest.raises(KeyError):
        registry[STATE_MISSING_NAME]  # pylint:disable=pointless-statement


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


async def test_context_resolver_ignored_keys():
    context_resolver = ContextResolver(app=FastAPI(), workflow_name="", state_name="")
    await context_resolver.start()

    with pytest.raises(NotAllowedContextKeyError):
        await context_resolver.set(ReservedContextKeys.EXCEPTION, "value")

    await context_resolver.set(
        ReservedContextKeys.EXCEPTION, "value", set_reserved=True
    )

    await context_resolver.shutdown()


async def test_reserved_context_keys():
    user_defined_keys: set[str] = set()
    for key_name, value in ReservedContextKeys.__dict__.items():
        if isinstance(value, str) and not key_name.startswith("_"):
            user_defined_keys.add(value)

    assert (
        user_defined_keys == ReservedContextKeys.RESERVED
    ), "please make sure all defined keys are also listed inside RESERVED"


async def test_run_workflow():
    context_resolver = ContextResolver(
        app=FastAPI(), workflow_name="unique", state_name="first"
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

    async def debug_print(state, event) -> None:
        print(f"{state=}, {event=}")

    await workflow_runner(
        state_registry=state_registry,
        context_resolver=context_resolver,
        before_event=debug_print,
        after_event=debug_print,
    )
    print(context_resolver)

    await context_resolver.shutdown()


async def test_workflow_manager():
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

    async def debug_print(state, event) -> None:
        print(f"{state=}, {event=}")
        # TODO: these need to be tested!

    workflow_manager = WorkflowManager(
        app=FastAPI(),
        state_registry=state_registry,
        before_event=debug_print,
        after_event=debug_print,
    )

    # ok workflow
    await workflow_manager.run_workflow(workflow_name="start_first", state_name="first")
    assert "start_first" in workflow_manager._workflow_context
    assert "start_first" in workflow_manager._workflow_tasks
    await workflow_manager.wait_workflow("start_first")
    assert "start_first" not in workflow_manager._workflow_context
    assert "start_first" not in workflow_manager._workflow_tasks

    # cancel workflow
    await workflow_manager.run_workflow(workflow_name="start_first", state_name="first")
    await workflow_manager.cancel_workflow("start_first")
    assert "start_first" not in workflow_manager._workflow_context
    assert "start_first" not in workflow_manager._workflow_tasks
    with pytest.raises(WorkflowNotFoundException):
        await workflow_manager.wait_workflow("start_first")


async def test_workflow_manager_error_handling():
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
    workflow_manager = WorkflowManager(app=FastAPI(), state_registry=state_registry)
    await workflow_manager.run_workflow(
        workflow_name=workflow_name, state_name="case_1_rasing_error"
    )
    await workflow_manager.wait_workflow(workflow_name)

    # CASE 2
    workflow_manager = WorkflowManager(app=FastAPI(), state_registry=state_registry)
    await workflow_manager.run_workflow(
        workflow_name=workflow_name, state_name="case_2_raising_error"
    )
    with pytest.raises(RuntimeError):
        await workflow_manager.wait_workflow(workflow_name)
