from typing import Any

import pytest
from models_library.api_schemas_dynamic_sidecar.containers import InactivityResponse
from pydantic import ValidationError, parse_obj_as


@pytest.mark.parametrize(
    "data, will_raise",
    [
        pytest.param(
            {"is_inactivity": True, "seconds_inactive": None},
            True,
            id="mark_as_inactive_when_inactivity_was_not_defined",
        ),
        pytest.param(
            {"is_inactivity": False, "seconds_inactive": None},
            False,
            id="seconds_inactive_none_when_is_inactivity_false",
        ),
        pytest.param(
            {"is_inactivity": True, "seconds_inactive": 1},
            False,
            id="accepted_values",
        ),
        pytest.param(
            {"is_inactivity": True, "seconds_inactive": -1},
            True,
            id="negative_seconds_inactive_provided",
        ),
    ],
)
def test_expected(data: dict[str, Any], will_raise: bool):
    if will_raise:
        with pytest.raises(ValidationError):
            parse_obj_as(InactivityResponse, data)
    else:
        parse_obj_as(InactivityResponse, data)
