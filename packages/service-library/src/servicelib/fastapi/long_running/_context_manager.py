import asyncio
from asyncio.log import logger
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import AnyHttpUrl

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

    def __init__(self, progress_update: Optional[Callable[[str, float], None]]) -> None:
        self._callable = progress_update
        self._last_message: Optional[str] = None
        self._last_percent: Optional[float] = None

    def update(
        self, *, message: Optional[str] = None, percent: Optional[float] = None
    ) -> None:
        if self._callable is None:
            return

        has_changes = False

        if message is not None and self._last_message != message:
            self._last_message = message
            has_changes = True
        if percent is not None and self._last_percent != percent:
            self._last_percent = percent
            has_changes = True

        if has_changes:
            self._callable(self._last_message, self._last_percent)


@asynccontextmanager
async def task_result(
    app: FastAPI,  # pass a client here
    async_client: AsyncClient,
    base_url: AnyHttpUrl,  # result, status, delete paths http://dy-sidecar/v1/some-route
    task_id: TaskId,
    *,
    timeout: float,
    progress: Optional[Callable[[str, float], None]] = None,
) -> AsyncIterator[Optional[Any]]:
    """
    raises: `TaskClientResultErrorError` if the timeout is reached
    raises: `asyncio.TimeoutError`, when this is raised the task removed on remote
    """
    client: Client = app.state.long_running_client

    progress_manager = _ProgressManager(progress)

    async def _status_update() -> TaskStatus:
        task_status = await client.get_task_status(async_client, base_url, task_id)
        logger.info("Task status %s", task_status.json())
        progress_manager.update(
            message=task_status.task_progress.message,
            percent=task_status.task_progress.percent,
        )
        return task_status

    async def _wait_task_completion() -> None:
        task_status = await _status_update()
        while not task_status.done:
            await asyncio.sleep(client.status_poll_interval)
            task_status = await _status_update()

    try:
        await asyncio.wait_for(_wait_task_completion(), timeout=timeout)

        result: Optional[Any] = await client.get_task_result(
            async_client, base_url, task_id
        )
        yield result
    except asyncio.TimeoutError as e:
        await client.cancel_and_delete_task(async_client, base_url, task_id)
        raise TaskClientTimeoutError(
            task_id=task_id, timeout=timeout, exception=e
        ) from e
