from typing import Any

import pytest
from models_library.api_schemas_dynamic_sidecar.containers import InactivityResponse


@pytest.mark.parametrize(
    "data, is_inactive",
    [
        pytest.param({"seconds_inactive": None}, False),
        pytest.param({"seconds_inactive": 0}, True),
        pytest.param({"seconds_inactive": 100}, True),
    ],
)
def test_expected(data: dict[str, Any], is_inactive: bool):
    assert InactivityResponse.parse_obj(data).is_inactive == is_inactive
