# pylint:disable=redefined-outer-name

from datetime import timedelta

import pytest
from simcore_service_dynamic_sidecar.modules.service_liveness import (
    CouldNotReachServiceError,
    wait_for_service_liveness,
)


@pytest.fixture
def check_interval() -> timedelta:
    return timedelta(seconds=0.1)


@pytest.fixture
def timeout() -> timedelta:
    return timedelta(seconds=1)


@pytest.mark.parametrize("handler_return", [None, True])
async def test_wait_for_service_liveness_ok(
    check_interval: timedelta, timeout: timedelta, handler_return: bool | None
):
    async def _ok_handler() -> bool | None:
        return handler_return

    await wait_for_service_liveness(
        _ok_handler,
        service_name="test_service",
        endpoint="http://fake.endpoint_string",
        check_interval=check_interval,
        timeout=timeout,
    )


@pytest.mark.parametrize("handler_return", [Exception("Ohh no, I failed!"), False])
async def test_wait_for_service_liveness_fails(
    check_interval: timedelta,
    timeout: timedelta,
    handler_return: bool | type[Exception],
):
    async def _failing_handler() -> bool:
        if isinstance(handler_return, bool):
            return handler_return
        raise handler_return

    with pytest.raises(CouldNotReachServiceError) as exc_info:
        await wait_for_service_liveness(
            _failing_handler,
            service_name="test_service",
            endpoint="http://fake.endpoint_string",
            check_interval=check_interval,
            timeout=timeout,
        )
    assert "Could not contact service" in f"{exc_info.value}"
