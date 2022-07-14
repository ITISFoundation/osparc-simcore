from typing import Any, Optional

import pytest
from pydantic import ValidationError
from servicelib.fastapi.long_running_tasks._models import TaskResult


@pytest.mark.parametrize(
    "result,error, raise_error",
    [
        (None, None, True),
        (None, "error", False),
        ("result", None, False),
        ("result", "error", True),
    ],
)
def test_expect_error_or_result(
    result: Optional[Any], error: Optional[Any], raise_error: bool
) -> None:
    if raise_error:
        with pytest.raises(ValidationError) as exec_info:
            TaskResult(result=result, error=error)
        assert isinstance(exec_info.value, ValidationError)
        assert (
            exec_info.value.errors()[0]["msg"]
            == f"Please provide either an {result=} or a {error=}"
        )
    else:
        assert TaskResult(result=result, error=error)
