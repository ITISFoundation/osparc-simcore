# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from typing import AsyncIterator, Final, Optional

import pytest
from fastapi import FastAPI
from pydantic import PositiveFloat
from pytest import LogCaptureFixture
from simcore_service_agent.core.application import create_app
from simcore_service_agent.modules.task_monitor import (
    JobAlreadyRegisteredError,
    TaskMonitor,
    disable_volume_removal_task,
    enable_volume_removal_task_if_missing,
)

REPEAT_TASK_INTERVAL_S: Final[PositiveFloat] = 0.05


async def _job_which_raises_error() -> None:
    raise RuntimeError("raised expected error")


async def _job_which_hangs() -> None:
    print("I will be hanging....")
    await asyncio.sleep(REPEAT_TASK_INTERVAL_S * 10000)


@pytest.mark.parametrize("repeat_interval_s", [REPEAT_TASK_INTERVAL_S, None])
async def test_task_monitor_recovers_from_error(
    caplog_debug: LogCaptureFixture,
    repeat_interval_s: Optional[PositiveFloat],
):

    task_monitor = TaskMonitor()
    task_monitor.register_job(
        _job_which_raises_error, repeat_interval_s=repeat_interval_s
    )

    await task_monitor.start()

    await asyncio.sleep(REPEAT_TASK_INTERVAL_S * 2)

    await task_monitor.shutdown()
    assert len(task_monitor._tasks) == 0
    assert len(task_monitor._to_start) == 0

    log_messages = caplog_debug.text
    print(log_messages)

    assert f"Starting '{_job_which_raises_error.__name__}' ..." in log_messages
    assert 'RuntimeError("raised expected error")' in log_messages
    assert (
        f"Will run '{_job_which_raises_error.__name__}' again in {repeat_interval_s} seconds"
        in log_messages
    )
    if repeat_interval_s is None:
        assert (
            f"Unexpected termination of '{_job_which_raises_error.__name__}'; it will be restarted"
            in log_messages
        )


async def test_add_same_task_fails():
    task_monitor = TaskMonitor()
    task_monitor.register_job(_job_which_raises_error, repeat_interval_s=1)
    with pytest.raises(JobAlreadyRegisteredError):
        task_monitor.register_job(_job_which_raises_error, repeat_interval_s=1)


async def test_hanging_jobs_are_detected():
    task_monitor = TaskMonitor()
    task_monitor.register_job(
        _job_which_hangs, repeat_interval_s=REPEAT_TASK_INTERVAL_S
    )
    await task_monitor.start()

    assert task_monitor.are_tasks_hanging is False

    await asyncio.sleep(REPEAT_TASK_INTERVAL_S * 2)

    assert task_monitor.are_tasks_hanging is True


@pytest.mark.parametrize("start_monitor", [True, False])
async def test_unregister_job(start_monitor: bool):
    task_monitor = TaskMonitor()
    task_monitor.register_job(_job_which_raises_error)

    if start_monitor:
        await task_monitor.start()

    if start_monitor:
        assert _job_which_raises_error.__name__ in task_monitor._tasks
    else:
        assert _job_which_raises_error.__name__ not in task_monitor._tasks

    assert _job_which_raises_error.__name__ in task_monitor._to_start
    await task_monitor.unregister_job(_job_which_raises_error)
    assert _job_which_raises_error.__name__ not in task_monitor._to_start
    assert _job_which_raises_error.__name__ not in task_monitor._tasks


@pytest.fixture
async def initialized_app(env: None) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app()

    await app.router.startup()
    yield app
    await app.router.shutdown()


async def test_disable_enable_volume_removal_task_workflow(
    initialized_app: FastAPI, caplog_debug: LogCaptureFixture
):
    task_monitor: TaskMonitor = initialized_app.state.task_monitor

    job_name = "backup_and_remove_volumes"

    assert job_name in task_monitor._to_start
    assert job_name in task_monitor._tasks

    await disable_volume_removal_task(initialized_app)
    assert job_name not in task_monitor._to_start
    assert job_name not in task_monitor._tasks
    await enable_volume_removal_task_if_missing(initialized_app)

    assert job_name in task_monitor._to_start
    assert job_name in task_monitor._tasks

    test_log_message = "was already registered."
    assert test_log_message not in caplog_debug.text
    await enable_volume_removal_task_if_missing(initialized_app)
    assert test_log_message in caplog_debug.text

    assert job_name in task_monitor._to_start
    assert job_name in task_monitor._tasks
