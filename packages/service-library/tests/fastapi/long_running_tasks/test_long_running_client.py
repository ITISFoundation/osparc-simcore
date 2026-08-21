from typing import Any

import pytest
from fastapi import FastAPI
from httpx import HTTPError
from servicelib.fastapi.long_running_tasks._client import (
    ClientConfiguration,
    retry_on_http_errors,
    setup,
)


def test_setup_configures_client_immediately():
    app = FastAPI()

    setup(app, router_prefix="/api", http_requests_timeout=2)

    assert app.state.long_running_client_configuration == ClientConfiguration(router_prefix="/api", default_timeout=2)


@pytest.mark.parametrize(
    "error_class, error_args",
    [
        (HTTPError, {"message": ""}),
    ],
)
async def test_retry_on_errors(error_class: type[Exception], error_args: dict[str, Any]):
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
