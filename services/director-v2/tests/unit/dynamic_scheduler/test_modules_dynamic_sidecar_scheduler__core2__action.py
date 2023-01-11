from typing import Any

from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._action import (
    Action,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._core2._marker import (
    mark_step,
)


async def test_action_ok():
    @mark_step
    async def print_info() -> dict[str, Any]:
        print("some info")
        return {}

    @mark_step
    async def verify(x: float, y: int) -> dict[str, Any]:
        assert type(x) == float
        assert type(y) == int
        return {}

    INFO_CHECK = Action(
        name="test",
        steps=[
            print_info,
            verify,
        ],
        next_action=None,
        on_error_action=None,
    )
    assert INFO_CHECK
