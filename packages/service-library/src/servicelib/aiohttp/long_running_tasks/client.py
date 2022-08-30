import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Coroutine, Final, Optional

from aiohttp import ClientConnectionError, ClientSession, web
from pydantic import Json
from tenacity import TryAgain, retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed, wait_random_exponential
from yarl import URL

from ..rest_responses import unwrap_envelope
from .server import TaskGet, TaskId, TaskProgress, TaskStatus

RequestBody = Json

_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE


_DEFAULT_AIOHTTP_RETRY_POLICY = dict(
    retry=retry_if_exception_type(ClientConnectionError),
    wait=wait_random_exponential(max=20),
    stop=stop_after_delay(30),
    reraise=True,
)


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _start(
    session: ClientSession, request: URL, json: Optional[RequestBody]
) -> TaskGet:
    async with session.post(request, json=json) as response:
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


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _task_result(session: ClientSession, result_href: str) -> Any:
    async with session.get(result_href) as response:
        response.raise_for_status()
        if response.status != web.HTTPNoContent.status_code:
            data, error = unwrap_envelope(await response.json())
            assert not error  # nosec
            assert data  # nosec
            return data


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _abort_task(session: ClientSession, abort_href: str) -> None:
    async with session.delete(abort_href) as response:
        response.raise_for_status()
        data, error = unwrap_envelope(await response.json())
        assert not error  # nosec
        assert not data  # nosec


@dataclass(frozen=True)
class LRTask:
    progress: TaskProgress
    _result: Optional[Coroutine[Any, Any, Any]] = None

    def done(self) -> bool:
        return self._result is not None

    async def result(self) -> Any:
        if not self._result:
            raise ValueError("No result ready!")
        return await self._result


async def long_running_task_request(
    session: ClientSession,
    url: URL,
    json: Optional[RequestBody] = None,
    wait_timeout_s: int = 1 * _HOUR,
    wait_interval_s: float = 1,
) -> AsyncGenerator[LRTask, None]:
    """Will use the passed `ClientSession` to call an oSparc long
    running task `url` passing `json` as request body.
    NOTE: this follows the usual aiohttp client syntax, and will raise the same errors

    :param session: The client to use
    :type session: ClientSession
    :param url: The url to call. NOTE: the endpoint must follow oSparc long running task server syntax (202, then status, result urls)
    :type url: URL
    :param json: optional body as dictionary, defaults to None
    :type json: Optional[RequestBody], optional
    :param wait_timeout_s: after this timeout is reached and no result is ready will raise asyncio.TimeoutError, defaults to 1*_HOUR
    :type wait_timeout_s: int, optional
    :param wait_interval_s: will check for result every `wait_interval` seconds, defaults to 1
    :type wait_interval_s: float, optional
    :return: a task containing the final result
    :rtype: AsyncGenerator[LRTask, None]
    :yield: a task containing the current TaskProgress
    :rtype: Iterator[AsyncGenerator[LRTask, None]]
    """
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
            progress=last_progress, _result=_task_result(session, task.result_href)
        )

    except (asyncio.CancelledError, asyncio.TimeoutError):
        if task:
            await _abort_task(session, task.abort_href)
        raise
