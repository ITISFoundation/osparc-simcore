import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Coroutine, Final, Optional

from aiohttp import ClientConnectionError, ClientSession, web
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
    session: ClientSession,
    task_id: TaskId,
    status_url: str,
    wait_timeout_s: int,
    wait_interval_s: float,
) -> AsyncGenerator[TaskProgress, None]:
    try:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(wait_interval_s),
            stop=stop_after_delay(wait_timeout_s),
            reraise=True,
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
    except TryAgain as exc:
        # this is a timeout
        raise asyncio.TimeoutError(
            f"Long running task {task_id}, calling to {status_url} timed-out after {wait_timeout_s} seconds"
        ) from exc


@retry(
    retry=retry_if_exception_type(ClientConnectionError),
    wait=wait_exponential(min=1, max=10),
    reraise=True,
)
async def _task_result(session: ClientSession, result_href: str) -> Any:
    async with session.get(result_href) as response:
        response.raise_for_status()
        if response.status != web.HTTPNoContent.status_code:
            data, error = unwrap_envelope(await response.json())
            assert not error  # nosec
            assert data  # nosec
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


@dataclass(frozen=True)
class LRTask:
    progress: TaskProgress
    result: Optional[Coroutine[Any, Any, Any]] = None


async def long_running_task_request(
    session: ClientSession,
    url: URL,
    json: Optional[RequestBody] = None,
    wait_timeout_s: int = 1 * _HOUR,
    wait_interval_s: float = 1,
) -> AsyncGenerator[LRTask, None]:
    task = None
    try:
        task = await _start(session, url, json)
        last_progress = None
        async for task_progress in _wait_for_completion(
            session, task.task_id, task.status_href, wait_timeout_s, wait_interval_s
        ):
            last_progress = task_progress
            yield LRTask(progress=task_progress)
        assert last_progress  # nosec
        yield LRTask(
            progress=last_progress, result=_task_result(session, task.result_href)
        )

    except (asyncio.CancelledError, asyncio.TimeoutError):
        if task:
            await _abort_task(session, task.abort_href)
        raise
