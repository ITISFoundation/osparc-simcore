import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import AnyHttpUrl

from ._client import Client
from ._errors import TaskClientTimeoutError
from ._models import TaskId, TaskStatus


class ProgressUpdater:
    def __init__(self, progress_update: Optional[Callable[[str, float], None]]) -> None:
        self._callable = progress_update
        self._last_message: Optional[str] = None
        self._last_percent: Optional[float] = None

    def update(
        self, *, message: Optional[str] = None, percent: Optional[float] = None
    ) -> None:
        if self._callable is None:
            return

        params = {"message": None, "percent": None}

        if message is not None and self._last_message != message:
            self._last_message = message
            params["message"] = message
        if percent is not None and self._last_percent != percent:
            self._last_percent = percent
            params["percent"] = percent

        # if parameters have changed
        if set(params.values()) != {None}:
            self._callable(**params)


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
    # TODO: better way to recover the client?
    client: Client = app.state.long_running_client

    progress_helper = ProgressUpdater(progress)

    async def _status_update() -> TaskStatus:
        task_status = await client.get_task_status(async_client, base_url, task_id)
        progress_helper.update(
            message=task_status.progress.message, percent=task_status.progress.percent
        )
        return task_status

    async def _wait_task_completion() -> None:
        task_status = await _status_update()
        while not task_status.done:
            task_status = await _status_update()
            await asyncio.sleep(client.status_poll_interval)

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
