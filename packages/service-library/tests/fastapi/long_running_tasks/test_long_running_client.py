from typing import Any

import pytest
from httpx import HTTPError
from servicelib.fastapi.long_running_tasks._client import retry_on_http_errors


@pytest.mark.parametrize(
    "error_class, error_args",
    [
        (HTTPError, {"message": ""}),
    ],
)
async def test_retry_on_errors(
    error_class: type[Exception], error_args: dict[str, Any]
):
    class MockClient:
        def __init__(self) -> None:
            self.counter = 0

        @retry_on_http_errors
        async def mock_request(self) -> None:
            self.counter += 1
            raise error_class(**error_args)

    test_obj = MockClient()
    with pytest.raises(error_class):
        await test_obj.mock_request()

    assert test_obj.counter == 3
