from typing import Any

import pytest
from models_library.api_schemas_dynamic_sidecar.containers import InactivityResponse


@pytest.mark.parametrize(
    "data, is_active",
    [
        pytest.param({"seconds_inactive": None}, True),
        pytest.param({"seconds_inactive": 0}, False),
        pytest.param({"seconds_inactive": 100}, False),
    ],
)
def test_expected(data: dict[str, Any], is_active: bool):
    assert InactivityResponse.parse_obj(data).is_active == is_active
