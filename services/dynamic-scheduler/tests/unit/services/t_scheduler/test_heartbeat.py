# pylint:disable=redefined-outer-name

import asyncio
from collections.abc import Iterator
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from simcore_service_dynamic_scheduler.services.t_scheduler._heartbeat import (
    _run_with_heartbeat,
)

_SHORT_INTERVAL = timedelta(milliseconds=50)


@pytest.fixture
def mock_heartbeat() -> Iterator[MagicMock]:
    with patch("simcore_service_dynamic_scheduler.services.t_scheduler._heartbeat.activity") as mock_activity:
        yield mock_activity


async def test_returns_result():
    async def _work() -> str:
        return "ok"

    result = await _run_with_heartbeat(_work(), heartbeat_interval=_SHORT_INTERVAL)
    assert result == "ok"


async def test_returns_none():
    async def _work() -> None:
        pass

    result = await _run_with_heartbeat(_work(), heartbeat_interval=_SHORT_INTERVAL)
    assert result is None


async def test_propagates_exception():
    async def _work() -> str:
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="boom"):
        await _run_with_heartbeat(_work(), heartbeat_interval=_SHORT_INTERVAL)


async def test_heartbeat_called_for_slow_work(mock_heartbeat: MagicMock):
    async def _slow_work() -> str:
        await asyncio.sleep(0.2)
        return "done"

    result = await _run_with_heartbeat(_slow_work(), heartbeat_interval=_SHORT_INTERVAL)

    assert result == "done"
    assert mock_heartbeat.heartbeat.call_count >= 2


async def test_no_heartbeat_for_fast_work(mock_heartbeat: MagicMock):
    async def _fast_work() -> str:
        return "instant"

    result = await _run_with_heartbeat(_fast_work(), heartbeat_interval=_SHORT_INTERVAL)

    assert result == "instant"
    mock_heartbeat.heartbeat.assert_not_called()


async def test_cancellation_propagates_and_cancels_inner_task():
    inner_cancelled = asyncio.Event()

    async def _blocking_work() -> str:
        try:
            await asyncio.sleep(float("inf"))
        except asyncio.CancelledError:
            inner_cancelled.set()
            raise
        return "unreachable"

    task = asyncio.create_task(_run_with_heartbeat(_blocking_work(), heartbeat_interval=_SHORT_INTERVAL))
    # let the heartbeat loop start
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert inner_cancelled.is_set()


async def test_exception_from_work_does_not_trigger_heartbeat(mock_heartbeat: MagicMock):
    async def _instant_fail() -> str:
        msg = "fail fast"
        raise ValueError(msg)

    with pytest.raises(ValueError, match="fail fast"):
        await _run_with_heartbeat(_instant_fail(), heartbeat_interval=_SHORT_INTERVAL)

    mock_heartbeat.heartbeat.assert_not_called()


async def test_multiple_heartbeats_for_very_slow_work(mock_heartbeat: MagicMock):
    async def _very_slow() -> str:
        await asyncio.sleep(0.35)
        return "finally"

    result = await _run_with_heartbeat(_very_slow(), heartbeat_interval=_SHORT_INTERVAL)

    assert result == "finally"
    assert mock_heartbeat.heartbeat.call_count >= 5


async def test_preserves_return_type():
    async def _dict_work() -> dict[str, int]:
        return {"a": 1, "b": 2}

    result = await _run_with_heartbeat(_dict_work(), heartbeat_interval=_SHORT_INTERVAL)
    assert result == {"a": 1, "b": 2}
    assert isinstance(result, dict)
