import asyncio
import traceback
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

from pydantic import NonNegativeInt

from ._base_deferred_handler import BaseDeferredHandler, DeferredContext
from ._models import (
    TaskExecutionResult,
    TaskResultCancelledError,
    TaskResultError,
    TaskResultSuccess,
    TaskUID,
)


def _format_exception(e: BaseException) -> str:
    return f"{e.__class__.__module__}.{e.__class__.__name__}: {e}"


def _get_str_traceback(e: BaseException) -> str:
    return "".join(traceback.format_tb(e.__traceback__))


async def _get_task_with_timeout(coroutine: Coroutine, *, timeout: timedelta) -> Any:
    return await asyncio.wait_for(coroutine, timeout=timeout.total_seconds())


class WorkerTracker:
    def __init__(self, max_worker_count: NonNegativeInt) -> None:
        self._semaphore = asyncio.Semaphore(max_worker_count)

        self._tasks: dict[TaskUID, asyncio.Task] = {}

    def has_free_slots(self) -> bool:
        return not self._semaphore.locked()

    async def handle_run(
        self,
        deferred_handler: type[BaseDeferredHandler],
        task_uid: TaskUID,
        deferred_context: DeferredContext,
        timeout: timedelta,
    ) -> TaskExecutionResult:
        self._tasks[task_uid] = task = asyncio.create_task(
            _get_task_with_timeout(
                deferred_handler.run(deferred_context), timeout=timeout
            )
        )

        result_to_return: TaskExecutionResult

        try:
            task_result = await task
            result_to_return = TaskResultSuccess(value=task_result)
        except asyncio.CancelledError:
            result_to_return = TaskResultCancelledError()
        except Exception as e:  # pylint:disable=broad-exception-caught
            result_to_return = TaskResultError(
                error=_format_exception(e),
                str_traceback=_get_str_traceback(e),
            )

        self._tasks.pop(task_uid, None)

        return result_to_return

    def cancel_run(self, task_uid: TaskUID) -> bool:
        """Attempts to cancel the a task.
        It is important to note that the task might not be running in this instance.

        returns: True if it could cancel the task
        """
        # if an associated task exists it cancels it
        task: asyncio.Task | None = self._tasks.get(task_uid, None)
        if task:
            # NOTE: there is no need to await the task after cancelling it.
            # It is already awaited, by ``handle_run, which handles
            # it's result in case of cancellation.
            # As a side effect it produces a RuntimeWarning coroutine: '...' was never awaited
            # which cannot be suppressed
            task.cancel()
            return True
        return False

    async def __aenter__(self) -> "WorkerTracker":
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, *args):
        self._semaphore.release()
