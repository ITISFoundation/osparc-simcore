"""
Provides a convenient way to return the result given a TaskId.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Coroutine
from dataclasses import dataclass
from typing import Any, Final, TypeAlias

import httpx
from fastapi import status
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import TaskGet, TaskStatus
from tenacity import (
    AsyncRetrying,
    TryAgain,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_delay,
    wait_random_exponential,
)
from yarl import URL

from ...long_running_tasks._errors import TaskClientResultError
from ...long_running_tasks._models import (
    ClientConfiguration,
    ProgressCallback,
    ProgressMessage,
    ProgressPercent,
)
from ...long_running_tasks._task import TaskId, TaskResult
from ...rest_responses import unwrap_envelope_if_required
from ._client import DEFAULT_HTTP_REQUESTS_TIMEOUT, Client, setup
from ._context_manager import periodic_task_result

_logger = logging.getLogger(__name__)

RequestBody: TypeAlias = Any

_MINUTE: Final[int] = 60  # in secs
_HOUR: Final[int] = 60 * _MINUTE  # in secs
_DEFAULT_POLL_INTERVAL_S: Final[float] = 1
_DEFAULT_FASTAPI_RETRY_POLICY: dict[str, Any] = {
    "retry": retry_if_exception_type(httpx.RequestError),
    "wait": wait_random_exponential(max=20),
    "stop": stop_after_delay(60),
    "reraise": True,
    "before_sleep": before_sleep_log(_logger, logging.INFO),
}


@retry(**_DEFAULT_FASTAPI_RETRY_POLICY)
async def _start(
    session: httpx.AsyncClient, url: URL, json: RequestBody | None
) -> TaskGet:
    response = await session.post(f"{url}", json=json)
    response.raise_for_status()
    data = unwrap_envelope_if_required(response.json())
    return TaskGet.model_validate(data)


@retry(**_DEFAULT_FASTAPI_RETRY_POLICY)
async def _wait_for_completion(
    session: httpx.AsyncClient,
    task_id: TaskId,
    status_url: URL,
    client_timeout: int,
) -> AsyncGenerator[TaskProgress, None]:
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(client_timeout),
            reraise=True,
            retry=retry_if_exception_type(TryAgain),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        ):
            with attempt:
                response = await session.get(f"{status_url}")
                response.raise_for_status()
                data = unwrap_envelope_if_required(response.json())
                task_status = TaskStatus.model_validate(data)

                yield task_status.task_progress
                if not task_status.done:
                    await asyncio.sleep(
                        float(
                            response.headers.get(
                                "retry-after", _DEFAULT_POLL_INTERVAL_S
                            )
                        )
                    )
                    msg = f"{task_id=}, {task_status.started=} has status: '{task_status.task_progress.message}' {task_status.task_progress.percent}%"
                    raise TryAgain(msg)  # noqa: TRY301

    except TryAgain as exc:
        # this is a timeout
        msg = f"Long running task {task_id}, calling to {status_url} timed-out after {client_timeout} seconds"
        raise TimeoutError(msg) from exc


@retry(**_DEFAULT_FASTAPI_RETRY_POLICY)
async def _task_result(session: httpx.AsyncClient, result_url: URL) -> Any:
    response = await session.get(f"{result_url}", params={"return_exception": True})
    response.raise_for_status()
    if response.status_code != status.HTTP_204_NO_CONTENT:
        return unwrap_envelope_if_required(response.json())
    return None


@retry(**_DEFAULT_FASTAPI_RETRY_POLICY)
async def _abort_task(session: httpx.AsyncClient, abort_url: URL) -> None:
    response = await session.delete(f"{abort_url}")
    response.raise_for_status()


@dataclass(frozen=True)
class LRTask:
    progress: TaskProgress
    _result: Coroutine[Any, Any, Any] | None = None

    def done(self) -> bool:
        return self._result is not None

    async def result(self) -> Any:
        if not self._result:
            msg = "No result ready!"
            raise ValueError(msg)
        return await self._result


async def long_running_task_request(
    session: httpx.AsyncClient,
    url: URL,
    json: RequestBody | None = None,
    client_timeout: int = 1 * _HOUR,
) -> AsyncGenerator[LRTask, None]:
    """Will use the passed `httpx.AsyncClient` to call an oSparc long
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
            URL(task.status_href),
            client_timeout,
        ):
            last_progress = task_progress
            yield LRTask(progress=task_progress)
        assert last_progress  # nosec
        yield LRTask(
            progress=last_progress,
            _result=_task_result(session, URL(task.result_href)),
        )

    except (TimeoutError, asyncio.CancelledError):
        if task:
            await _abort_task(session, URL(task.abort_href))
        raise


__all__: tuple[str, ...] = (
    "DEFAULT_HTTP_REQUESTS_TIMEOUT",
    "Client",
    "ClientConfiguration",
    "ProgressCallback",
    "ProgressMessage",
    "ProgressPercent",
    "TaskClientResultError",
    "TaskId",
    "TaskResult",
    "periodic_task_result",
    "setup",
)
# nopycln: file
