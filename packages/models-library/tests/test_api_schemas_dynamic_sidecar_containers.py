from typing import Any

import pytest
from models_library.api_schemas_dynamic_sidecar.containers import ActivityInfo


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"seconds_inactive": None}),
        pytest.param({"seconds_inactive": 0}),
        pytest.param({"seconds_inactive": 100}),
    ],
)
def test_activity_info(data: dict[str, Any]):
    assert ActivityInfo.parse_obj(data)
