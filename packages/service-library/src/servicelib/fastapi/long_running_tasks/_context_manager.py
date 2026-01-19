import asyncio
import logging
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final

from common_library.logging.logging_errors import create_troubleshooting_log_message
from pydantic import PositiveFloat
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

from ...long_running_tasks.errors import TaskClientTimeoutError, TaskExceptionError
from ...long_running_tasks.models import (
    ProgressCallback,
    ProgressMessage,
    ProgressPercent,
    TaskId,
    TaskStatus,
)
from ._client import HttpClient

_logger = logging.getLogger(__name__)

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
        update_callback: ProgressCallback | None,
    ) -> None:
        self._callback = update_callback
        self._last_message: ProgressMessage | None = None
        self._last_percent: ProgressPercent | None = None

    async def update(
        self,
        task_id: TaskId,
        *,
        message: ProgressMessage | None = None,
        percent: ProgressPercent | None = None,
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
            await self._callback(
                self._last_message or "",
                self._last_percent,
                task_id,
            )


@asynccontextmanager
async def periodic_task_result(
    client: HttpClient,
    task_id: TaskId,
    *,
    task_timeout: PositiveFloat,
    progress_callback: ProgressCallback | None = None,
    status_poll_interval: PositiveFloat = 5,
) -> AsyncIterator[Any | None]:
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

    raises: the original exception the task raised, if any
    raises: `asyncio.TimeoutError` NOTE: the remote task will also be removed
    """

    warnings.warn(
        "This context manager is deprecated and will be removed in future releases. "
        "Please use the `servicelib.long_running_tasks.lrt_api` instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    progress_manager = _ProgressManager(progress_callback)

    @retry(
        wait=wait_exponential(max=1),
        stop=stop_after_attempt(3),
        reraise=True,
        before_sleep=before_sleep_log(_logger, logging.WARNING, exc_info=True),
    )
    async def _status_update() -> TaskStatus:
        task_status: TaskStatus = await client.get_task_status(task_id)
        _logger.debug("Task status %s", task_status.model_dump_json())
        await progress_manager.update(
            task_id=task_id,
            message=task_status.task_progress.message,
            percent=task_status.task_progress.percent,
        )
        return task_status

    async def _wait_for_task_result() -> Any:
        task_status = await _status_update()
        while not task_status.done:
            await asyncio.sleep(status_poll_interval)
            task_status = await _status_update()

        return await client.get_task_result(task_id)

    try:
        result = await asyncio.wait_for(_wait_for_task_result(), timeout=task_timeout)
        _logger.debug("%s, %s", f"{task_id=}", f"{result=}")

        yield result
    except TimeoutError as e:
        await client.remove_task(task_id)
        raise TaskClientTimeoutError(
            task_id=task_id,
            timeout=task_timeout,
            exception=e,
        ) from e
    except Exception as e:
        _logger.warning(
            create_troubleshooting_log_message(
                user_error_msg=f"{task_id=} raised an exception",
                error=e,
                tip=f"Check the logs of the service responding to '{client.base_url}'",
            )
        )
        raise TaskExceptionError(task_id=task_id, exception=e, traceback="") from e
