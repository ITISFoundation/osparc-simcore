from typing import Any

import pytest
from models_library.callbacks_mapping import (
    INACTIVITY_TIMEOUT_CAP,
    TIMEOUT_MIN,
    CallbacksMapping,
)
from pydantic import ValidationError, parse_obj_as


def _format_with_timeout(timeout: float) -> dict[str, Any]:
    return {"inactivity": {"service": "a-service", "command": "", "timeout": timeout}}


def test_inactivity_time_out_is_max_capped():
    for in_bounds in [
        TIMEOUT_MIN,
        TIMEOUT_MIN + 1,
        INACTIVITY_TIMEOUT_CAP - 1,
        INACTIVITY_TIMEOUT_CAP,
    ]:
        parse_obj_as(CallbacksMapping, _format_with_timeout(in_bounds))

    for out_of_bounds in [INACTIVITY_TIMEOUT_CAP + 1, TIMEOUT_MIN - 1]:
        with pytest.raises(ValidationError):
            parse_obj_as(CallbacksMapping, _format_with_timeout(out_of_bounds))
