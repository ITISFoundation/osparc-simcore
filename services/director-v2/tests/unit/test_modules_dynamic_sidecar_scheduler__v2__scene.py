from typing import Any

import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._marker import (
    mark_action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._scene import (
    PlayCatalog,
    Scene,
)


async def test_state_ok():
    @mark_action
    async def print_info() -> dict[str, Any]:
        print("some info")
        return {}

    @mark_action
    async def verify(x: float, y: int) -> dict[str, Any]:
        assert type(x) == float
        assert type(y) == int
        return {}

    INFO_CHECK = Scene(
        name="test",
        actions=[
            print_info,
            verify,
        ],
        next_scene=None,
        on_error_scene=None,
    )
    assert INFO_CHECK


def test_state_registry():
    STATE_ONE_NAME = "one"
    STATE_TWO_NAME = "two"
    STATE_MISSING_NAME = "not_existing_state"

    state_one = Scene(
        name=STATE_ONE_NAME, actions=[], next_scene=None, on_error_scene=None
    )
    state_two = Scene(
        name=STATE_TWO_NAME, actions=[], next_scene=None, on_error_scene=None
    )

    registry = PlayCatalog(
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
