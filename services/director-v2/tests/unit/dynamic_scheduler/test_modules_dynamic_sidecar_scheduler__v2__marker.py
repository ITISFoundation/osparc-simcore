from typing import Any

import pytest
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._errors import (
    UnexpectedStepReturnTypeError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.scheduler._v2._marker import (
    mark_step,
)


async def test_register_step_with_return_value():
    @mark_step
    async def return_inputs(x: str, y: float, z: dict[str, int]) -> dict[str, Any]:
        return {"x": x, "y": y, "z": z}

    assert return_inputs.input_types == {"x": str, "y": float, "z": dict[str, int]}

    assert await return_inputs(1, 2, {"a": 3}) == dict(x=1, y=2, z={"a": 3})


async def test_register_step_wrong_return_type():
    with pytest.raises(UnexpectedStepReturnTypeError) as exec_info:

        @mark_step
        async def wrong_return_type(x: str, y: float, z: dict[str, int]) -> str:
            return {"x": x, "y": y, "z": z}

    assert (
        f"{exec_info.value}"
        == "Step should always return `dict[str, Any]`, returning: <class 'str'>"
    )
