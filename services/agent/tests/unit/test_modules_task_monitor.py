import asyncio
from typing import Final, Optional

import pytest
from pydantic import PositiveFloat
from pytest import LogCaptureFixture
from simcore_service_agent.modules.task_monitor import TaskMonitor

REPEAT_TASK_INTERVAL_S: Final[PositiveFloat] = 0.05


@pytest.mark.parametrize("repeat_interval_s", [REPEAT_TASK_INTERVAL_S, None])
async def test_app_recovers_from_error(
    caplog_info_debug: LogCaptureFixture,
    repeat_interval_s: Optional[PositiveFloat],
):
    async def _error_raising_job() -> None:
        raise RuntimeError("raised expected error")

    task_monitor = TaskMonitor()
    task_monitor.register_job(_error_raising_job, repeat_interval_s=repeat_interval_s)

    await task_monitor.start()

    await asyncio.sleep(REPEAT_TASK_INTERVAL_S * 2)

    await task_monitor.shutdown()

    log_messages = caplog_info_debug.text
    print(log_messages)

    assert f"Running '{_error_raising_job.__name__}'" in log_messages
    assert 'RuntimeError("raised expected error")' in log_messages
    assert (
        f"Will run '{_error_raising_job.__name__}' again in {repeat_interval_s} seconds"
        in log_messages
    )
    if repeat_interval_s is None:
        assert (
            f"Unexpected termination of '{_error_raising_job.__name__}'; it will be restarted"
            in log_messages
        )
