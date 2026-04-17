# pylint:disable=redefined-outer-name

import asyncio
from unittest.mock import AsyncMock

import pytest
import tenacity
from simcore_service_dynamic_scheduler.services.t_scheduler._health_check import (
    TemporalHealthCheck,
    wait_till_temporalio_is_responsive,
)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.service_client.check_health = AsyncMock(return_value=True)
    return client


async def test_temporal_health_check_ping_healthy(mock_client: AsyncMock):
    health_check = TemporalHealthCheck(mock_client)
    assert await health_check.ping() is True
    mock_client.service_client.check_health.assert_called_once()


async def test_temporal_health_check_ping_unhealthy(mock_client: AsyncMock):
    mock_client.service_client.check_health = AsyncMock(side_effect=Exception("connection refused"))
    health_check = TemporalHealthCheck(mock_client)
    assert await health_check.ping() is False


async def test_temporal_health_check_setup_and_shutdown(mock_client: AsyncMock):
    health_check = TemporalHealthCheck(mock_client)
    assert health_check.is_healthy is False

    await health_check.setup()
    # give the periodic task time to run at least once
    await asyncio.sleep(0.1)
    assert health_check.is_healthy is True

    await health_check.shutdown()


async def test_temporal_health_check_detects_degradation(mock_client: AsyncMock):
    health_check = TemporalHealthCheck(mock_client)
    await health_check.setup()
    await asyncio.sleep(0.1)
    assert health_check.is_healthy is True

    # simulate Temporal becoming unreachable
    mock_client.service_client.check_health = AsyncMock(side_effect=Exception("connection refused"))
    # wait for the periodic task to pick up the change
    await asyncio.sleep(6)
    assert health_check.is_healthy is False

    await health_check.shutdown()


async def test_wait_till_temporalio_is_responsive_success(mock_client: AsyncMock):
    await wait_till_temporalio_is_responsive(mock_client)
    mock_client.service_client.check_health.assert_called_once()


async def test_wait_till_temporalio_is_responsive_retries_then_succeeds(
    mock_client: AsyncMock,
):
    call_count = 0

    async def _check_health(**kwargs) -> bool:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            msg = "not ready"
            raise Exception(msg)  # noqa: TRY002
        return True

    mock_client.service_client.check_health = _check_health

    await wait_till_temporalio_is_responsive(mock_client)
    assert call_count == 3


async def test_wait_till_temporalio_is_responsive_times_out(mock_client: AsyncMock):
    mock_client.service_client.check_health = AsyncMock(side_effect=Exception("permanently unavailable"))

    # Patch the retry decorator to use a short timeout for testing
    original_retry = wait_till_temporalio_is_responsive.retry
    wait_till_temporalio_is_responsive.retry = original_retry.copy(stop=tenacity.stop_after_delay(3))
    try:
        with pytest.raises(Exception, match="permanently unavailable"):
            await wait_till_temporalio_is_responsive(mock_client)
    finally:
        wait_till_temporalio_is_responsive.retry = original_retry
