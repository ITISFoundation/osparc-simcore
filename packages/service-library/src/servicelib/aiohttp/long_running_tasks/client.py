import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Coroutine, Final, Optional

from aiohttp import ClientConnectionError, ClientSession, web
from pydantic import Json
from tenacity import TryAgain, retry
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential
from yarl import URL

from ..rest_responses import unwrap_envelope
from .server import TaskGet, TaskId, TaskProgress, TaskStatus

RequestBody = Json

_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE
_DEFAULT_POLL_INTERVAL_S: Final[float] = 1
_DEFAULT_AIOHTTP_RETRY_POLICY = dict(
    retry=retry_if_exception_type(ClientConnectionError),
    wait=wait_random_exponential(max=20),
    stop=stop_after_delay(30),
    reraise=True,
)


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _start(
    session: ClientSession, url: URL, json: Optional[RequestBody]
) -> TaskGet:
    async with session.post(url, json=json) as response:
        response.raise_for_status()
        data, error = unwrap_envelope(await response.json())
    assert not error  # nosec
    assert data is not None  # nosec
    task = TaskGet.parse_obj(data)
    return task


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _wait_for_completion(
    session: ClientSession,
    task_id: TaskId,
    status_url: URL,
    client_timeout: int,
) -> AsyncGenerator[TaskProgress, None]:
    try:

        async for attempt in AsyncRetrying(
            stop=stop_after_delay(client_timeout),
            reraise=True,
            retry=retry_if_exception_type(TryAgain),
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
                    await asyncio.sleep(
                        float(
                            response.headers.get(
                                "retry-after", _DEFAULT_POLL_INTERVAL_S
                            )
                        )
                    )
                    raise TryAgain(
                        f"{task_id=}, {task_status.started=} has "
                        f"status: '{task_status.task_progress.message}'"
                        f" {task_status.task_progress.percent}%"
                    )
    except TryAgain as exc:
        # this is a timeout
        raise asyncio.TimeoutError(
            f"Long running task {task_id}, calling to {status_url} timed-out after {client_timeout} seconds"
        ) from exc


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _task_result(session: ClientSession, result_url: URL) -> Any:
    async with session.get(result_url) as response:
        response.raise_for_status()
        if response.status != web.HTTPNoContent.status_code:
            data, error = unwrap_envelope(await response.json())
            assert not error  # nosec
            assert data  # nosec
            return data


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _abort_task(session: ClientSession, abort_url: URL) -> None:
    async with session.delete(abort_url) as response:
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
    client_timeout: int = 1 * _HOUR,
) -> AsyncGenerator[LRTask, None]:
    """Will use the passed `ClientSession` to call an oSparc long
    running task `url` passing `json` as request body.
    NOTE: this follows the usual aiohttp client syntax, and will raise the same errors

    Raises:
        [https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions]
    """
    task = None
    try:
        task = await _start(session, url, json)
        last_progress = None
        async for task_progress in _wait_for_completion(
            session,
            task.task_id,
            url.with_path(task.status_href, encoded=True),
            client_timeout,
        ):
            last_progress = task_progress
            yield LRTask(progress=task_progress)
        assert last_progress  # nosec
        yield LRTask(
            progress=last_progress,
            _result=_task_result(
                session, url.with_path(task.result_href, encoded=True)
            ),
        )

    except (asyncio.CancelledError, asyncio.TimeoutError):
        if task:
            await _abort_task(session, url.with_path(task.abort_href, encoded=True))
        raise
