import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from aiohttp import ClientConnectionError, ClientSession
from tenacity import TryAgain, retry
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential
from yarl import URL

from ...long_running_tasks._constants import DEFAULT_POLL_INTERVAL_S, HOUR
from ...long_running_tasks.models import LRTask, RequestBody
from ...rest_responses import unwrap_envelope_if_required
from .. import status
from .server import TaskGet, TaskId, TaskProgress, TaskStatus

_logger = logging.getLogger(__name__)


_DEFAULT_AIOHTTP_RETRY_POLICY: dict[str, Any] = {
    "retry": retry_if_exception_type(ClientConnectionError),
    "wait": wait_random_exponential(max=20),
    "stop": stop_after_delay(60),
    "reraise": True,
    "before_sleep": before_sleep_log(_logger, logging.INFO),
}


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _start(session: ClientSession, url: URL, json: RequestBody | None) -> TaskGet:
    async with session.post(url, json=json) as response:
        response.raise_for_status()
        data = unwrap_envelope_if_required(await response.json())
    return TaskGet.model_validate(data)


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
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        ):
            with attempt:
                async with session.get(status_url) as response:
                    response.raise_for_status()
                    data = unwrap_envelope_if_required(await response.json())
                task_status = TaskStatus.model_validate(data)
                yield task_status.task_progress
                if not task_status.done:
                    await asyncio.sleep(
                        float(
                            response.headers.get("retry-after", DEFAULT_POLL_INTERVAL_S)
                        )
                    )
                    msg = f"{task_id=}, {task_status.started=} has status: '{task_status.task_progress.message}' {task_status.task_progress.percent}%"
                    raise TryAgain(msg)  # noqa: TRY301

    except TryAgain as exc:
        # this is a timeout
        msg = f"Long running task {task_id}, calling to {status_url} timed-out after {client_timeout} seconds"
        raise TimeoutError(msg) from exc


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _task_result(session: ClientSession, result_url: URL) -> Any:
    async with session.get(result_url) as response:
        response.raise_for_status()
        if response.status != status.HTTP_204_NO_CONTENT:
            return unwrap_envelope_if_required(await response.json())
        return None


@retry(**_DEFAULT_AIOHTTP_RETRY_POLICY)
async def _abort_task(session: ClientSession, abort_url: URL) -> None:
    async with session.delete(abort_url) as response:
        response.raise_for_status()


async def long_running_task_request(
    session: ClientSession,
    url: URL,
    json: RequestBody | None = None,
    client_timeout: int = 1 * HOUR,
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


__all__: tuple[str, ...] = ("LRTask",)
