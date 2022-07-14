import asyncio
from asyncio.log import logger
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from pydantic import PositiveFloat

from ._client import Client
from ._errors import TaskClientTimeoutError
from ._models import TaskId, TaskStatus


class _ProgressManager:
    """
    Avoids sending duplicate progress updates.

    When polling the status, the same progress messages can arrive in a row.
    This allows the client to filter out the flood of messages when it subscribes
    for progress updates.
    """

    def __init__(
        self, update_callback: Optional[Callable[[str, float], Awaitable[None]]]
    ) -> None:
        self._callback = update_callback
        self._last_message: Optional[str] = None
        self._last_percent: Optional[float] = None

    async def update(
        self, *, message: Optional[str] = None, percent: Optional[float] = None
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
            await self._callback(self._last_message, self._last_percent)


@asynccontextmanager
async def periodic_task_result(
    client: Client,
    task_id: TaskId,
    *,
    task_timeout: PositiveFloat,
    progress_callback: Optional[Callable[[str, float], Awaitable[None]]] = None,
    status_poll_interval: PositiveFloat = 5,
) -> AsyncIterator[Optional[Any]]:
    """
    A convenient wrapper around the Client. Polls for results and returns them
    once available.

    Parameters:
    - `client`: an istance of `long_running_tasks.client.Client`
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

    async def _status_update() -> TaskStatus:
        task_status = await client.get_task_status(task_id)
        logger.info("Task status %s", task_status.json())
        await progress_manager.update(
            message=task_status.task_progress.message,
            percent=task_status.task_progress.percent,
        )
        return task_status

    async def _wait_task_completion() -> None:
        task_status = await _status_update()
        while not task_status.done:
            await asyncio.sleep(status_poll_interval)
            task_status = await _status_update()

    try:
        await asyncio.wait_for(_wait_task_completion(), timeout=task_timeout)

        result: Optional[Any] = await client.get_task_result(task_id)
        yield result
    except asyncio.TimeoutError as e:
        task_removed = await client.cancel_and_delete_task(task_id)
        raise TaskClientTimeoutError(
            task_id=task_id,
            timeout=task_timeout,
            exception=e,
            task_removed=task_removed,
        ) from e
