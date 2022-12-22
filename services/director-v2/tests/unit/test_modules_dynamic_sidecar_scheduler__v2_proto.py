from typing import Any

import pytest
from fastapi import FastAPI
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._proto import (
    ContextResolver,
    State,
    StateRegistry,
    WorkflowTracker,
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


async def test_run_workflow():
    workflow_tracker = WorkflowTracker(name="random")
    context_resolver = ContextResolver(app=FastAPI())
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
            verify,
        ],
        next_state=None,
        on_error_state=None,
    )

    state_registry = StateRegistry(FIRST_STATE, SECOND_STATE)

    await workflow_runner(
        state_registry=state_registry,
        context_resolver=context_resolver,
        initial_state="first",
        workflow_tracker=workflow_tracker,
    )
    print(context_resolver)

    await context_resolver.shutdown()
