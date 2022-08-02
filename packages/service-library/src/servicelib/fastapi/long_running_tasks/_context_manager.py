import asyncio
from asyncio.log import logger
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, Final, Optional

from pydantic import PositiveFloat

from ...utils import logged_gather
from ._client import Client
from ._errors import TaskClientTimeoutError
from ._models import ProgressMessage, ProgressPercent, TaskId, TaskStatus

# NOTE: very short running requests are involved
MAX_CONCURRENCY: Final[int] = 10


class _ProgressManager:
    """
    Avoids sending duplicate progress updates.

    When polling the status, the same progress messages can arrive in a row.
    This allows the client to filter out the flood of messages when it subscribes
    for progress updates.
    """

    def __init__(
        self,
        update_callback: Optional[
            Callable[[ProgressMessage, ProgressPercent, TaskId], Awaitable[None]]
        ],
    ) -> None:
        self._callback = update_callback
        self._last_message: Optional[ProgressMessage] = None
        self._last_percent: Optional[ProgressPercent] = None

    async def update(
        self,
        task_id: TaskId,
        *,
        message: Optional[ProgressMessage] = None,
        percent: Optional[ProgressPercent] = None,
    ) -> None:
        if self._callback is None:
            return

        has_changes = False

        if message is not None and self._last_message != message:
            self._last_message = message
            has_changes = True
        if percent is not None and self._last_percent != percent:
            self._last_percent = percent
            has_changes = True

        if has_changes:
            await self._callback(self._last_message, self._last_percent, task_id)


@asynccontextmanager
async def periodic_tasks_results(
    client: Client,
    task_ids: list[TaskId],
    *,
    task_timeout: PositiveFloat,
    progress_callback: Optional[
        Callable[[ProgressMessage, ProgressPercent, TaskId], Awaitable[None]]
    ] = None,
    status_poll_interval: PositiveFloat = 5,
) -> AsyncIterator[list[Optional[Any]]]:
    """
    A convenient wrapper around the Client. Polls for results and returns them
    once available.

    Parameters:
    - `client`: an instance of `long_running_tasks.client.Client`
    - `task_ids`: a list of tasks to monitor and recover results from
    - `task_timeout`: when this expires the task will be cancelled and
        removed form the server
    - `progress` optional: user defined awaitable with two positional arguments:
        * first argument `message`, type `str`
        * second argument `percent`, type `float` between [0.0, 1.0]
    - `status_poll_interval` optional: when waiting for a task to finish,
        how frequent should the server be queried

    raises: `TaskClientResultError` if the task finished with an error instead of
        the expected result
    raises: `asyncio.TimeoutError` NOTE: the remote task will also be removed
    """

    progress_manager = _ProgressManager(progress_callback)

    async def _statuses_update() -> list[TaskStatus]:
        tasks_status: list[TaskStatus] = await logged_gather(
            *(client.get_task_status(task_id) for task_id in task_ids),
            max_concurrency=MAX_CONCURRENCY,
        )
        for task_id, task_status in zip(task_ids, tasks_status):
            logger.debug("Task status %s", task_status.json())
            await progress_manager.update(
                task_id=task_id,
                message=task_status.task_progress.message,
                percent=task_status.task_progress.percent,
            )

        return tasks_status

    async def _wait_tasks_completion() -> None:
        tasks_statuses = await _statuses_update()
        while not all(task_status.done for task_status in tasks_statuses):
            await asyncio.sleep(status_poll_interval)
            tasks_statuses = await _statuses_update()

    try:
        await asyncio.wait_for(_wait_tasks_completion(), timeout=task_timeout)

        results: list[Optional[Any]] = await logged_gather(
            *(client.get_task_result(task_id) for task_id in task_ids),
            max_concurrency=MAX_CONCURRENCY,
        )
        for result, task_id in zip(results, task_ids):
            logger.debug("Task %s result %s", task_id, result)

        yield results
    except asyncio.TimeoutError as e:
        tasks_removed: list[bool] = await logged_gather(
            *(client.cancel_and_delete_task(task_id) for task_id in task_ids),
            max_concurrency=MAX_CONCURRENCY,
        )
        raise TaskClientTimeoutError(
            task_ids=task_ids,
            timeout=task_timeout,
            exception=e,
            tasks_removed=tasks_removed,
        ) from e


@asynccontextmanager
async def periodic_task_result(
    client: Client,
    task_id: TaskId,
    *,
    task_timeout: PositiveFloat,
    progress_callback: Optional[
        Callable[[ProgressMessage, ProgressPercent, TaskId], Awaitable[None]]
    ] = None,
    status_poll_interval: PositiveFloat = 5,
) -> AsyncIterator[Optional[Any]]:
    """
    A convenient wrapper around the Client. Polls for results and returns them
    once available.

    Parameters:
    - `client`: an instance of `long_running_tasks.client.Client`
    - `task_id`: a task_id to monitor and recover result from
    - `task_timeout`: when this expires the task will be cancelled and
        removed form the server
    - `progress` optional: user defined awaitable with two positional arguments:
        * first argument `message`, type `str`
        * second argument `percent`, type `float` between [0.0, 1.0]
    - `status_poll_interval` optional: when waiting for a task to finish,
        how frequent should the server be queried

    raises: `TaskClientResultError` if the task finished with an error instead of
        the expected result
    raises: `asyncio.TimeoutError` NOTE: the remote task will also be removed
    """
    async with periodic_tasks_results(
        client=client,
        task_ids=[task_id],
        task_timeout=task_timeout,
        progress_callback=progress_callback,
        status_poll_interval=status_poll_interval,
    ) as results:
        yield results[0]
