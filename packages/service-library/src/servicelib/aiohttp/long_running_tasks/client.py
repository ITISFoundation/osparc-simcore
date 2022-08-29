import asyncio
from typing import Any, AsyncGenerator, Final, Optional

from aiohttp import ClientConnectionError, ClientSession
from tenacity import TryAgain, retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_exponential, wait_fixed
from yarl import URL

from ..rest_responses import unwrap_envelope
from .server import TaskGet, TaskId, TaskProgress, TaskStatus

RequestBody = dict[str, Any]


@retry(
    retry=retry_if_exception_type(ClientConnectionError),
    wait=wait_exponential(min=1, max=10),
    reraise=True,
)
async def _start(
    session: ClientSession, request: URL, data: Optional[RequestBody]
) -> TaskGet:
    async with session.post(request, data=data) as response:
        response.raise_for_status()
        data, error = unwrap_envelope(await response.json())
    assert not error  # nosec
    assert data is not None  # nosec
    task = TaskGet.parse_obj(data)
    return task


async def _wait_for_completion(
    session: ClientSession, task_id: TaskId, status_url: str, wait_timeout_s: int
) -> AsyncGenerator[TaskProgress, None]:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(1), stop=stop_after_delay(wait_timeout_s)
    ):
        with attempt:
            async with session.get(status_url) as response:
                response.raise_for_status()
                data, error = unwrap_envelope(await response.json())
                assert not error  # nosec
                assert data is not None  # nosec
            task_status = TaskStatus.parse_obj(data)
            yield task_status.task_progress
            if not task_status.done:
                raise TryAgain(
                    f"{task_id=}, {task_status.started=} has "
                    f"status: '{task_status.task_progress.message}'"
                    f" {task_status.task_progress.percent}%"
                )


@retry(
    retry=retry_if_exception_type(ClientConnectionError),
    wait=wait_exponential(min=1, max=10),
    reraise=True,
)
async def _get_task_result(session: ClientSession, result_href: str) -> Any:
    async with session.get(result_href) as response:
        response.raise_for_status()
        data, error = unwrap_envelope(await response.json())
        assert not error  # nosec
    return data


@retry(
    retry=retry_if_exception_type(ClientConnectionError),
    wait=wait_exponential(min=1, max=10),
    reraise=True,
)
async def _abort_task(session: ClientSession, abort_href: str) -> None:
    async with session.delete(abort_href) as response:
        response.raise_for_status()
        data, error = unwrap_envelope(await response.json())
        assert not error  # nosec
        assert not data  # nosec


_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE


async def long_running_task_request(
    session: ClientSession,
    request: URL,
    data: Optional[RequestBody] = None,
    wait_timeout_s: int = 1 * _HOUR,
) -> AsyncGenerator[TaskProgress, None]:
    task = None
    try:
        task = await _start(session, request, data)
        async for task_progress in _wait_for_completion(
            session, task.task_id, task.status_href, wait_timeout_s
        ):
            yield task_progress

        yield await _get_task_result(session, task.result_href)
    except asyncio.CancelledError:
        if task:
            await _abort_task(session, task.abort_href)
        raise
