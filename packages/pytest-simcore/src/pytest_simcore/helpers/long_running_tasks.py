# pylint: disable=protected-access

import pytest
from fastapi import FastAPI
from servicelib.long_running_tasks.errors import TaskNotFoundError
from servicelib.long_running_tasks.manager import (
    LongRunningManager,
)
from servicelib.long_running_tasks.models import TaskContext
from servicelib.long_running_tasks.task import TaskId
from tenacity import (
    AsyncRetrying,
    retry_if_not_exception_type,
    stop_after_delay,
    wait_fixed,
)


def get_fastapi_long_running_manager(app: FastAPI) -> LongRunningManager:
    manager = app.state.long_running_manager
    assert isinstance(manager, LongRunningManager)
    return manager


async def assert_task_is_no_longer_present(
    manager: LongRunningManager, task_id: TaskId, task_context: TaskContext
) -> None:
    async for attempt in AsyncRetrying(
        reraise=True,
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        retry=retry_if_not_exception_type(TaskNotFoundError),
    ):
        with attempt:  # noqa: SIM117
            with pytest.raises(TaskNotFoundError):
                # use internals to detirmine when it's no longer here
                await manager._tasks_manager._get_tracked_task(  # noqa: SLF001
                    task_id, task_context
                )
