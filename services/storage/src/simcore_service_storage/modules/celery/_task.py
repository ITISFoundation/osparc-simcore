import asyncio
import concurrent.futures
import inspect
import logging
from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
from typing import Any, Concatenate, Final, ParamSpec, TypeVar, overload

from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.abortable import (  # type: ignore[import-untyped]
    AbortableAsyncResult,
    AbortableTask,
)
from celery.exceptions import Ignore  # type: ignore[import-untyped]
from pydantic import NonNegativeInt
from servicelib.async_utils import cancel_wait_task

from . import get_event_loop
from .errors import encore_celery_transferrable_error
from .models import TaskID, TaskId
from .utils import get_fastapi_app

_logger = logging.getLogger(__name__)

_DEFAULT_TASK_TIMEOUT: Final[timedelta | None] = None
_DEFAULT_MAX_RETRIES: Final[NonNegativeInt] = 3
_DEFAULT_WAIT_BEFORE_RETRY: Final[timedelta] = timedelta(seconds=5)
_DEFAULT_DONT_AUTORETRY_FOR: Final[tuple[type[Exception], ...]] = ()
_DEFAULT_ABORT_TASK_TIMEOUT: Final[timedelta] = timedelta(seconds=0.5)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


class TaskAbortedError(Exception): ...


def _async_task_wrapper(
    app: Celery,
) -> Callable[
    [Callable[Concatenate[AbortableTask, TaskId, P], Coroutine[Any, Any, R]]],
    Callable[Concatenate[AbortableTask, P], R],
]:
    def decorator(
        coro: Callable[Concatenate[AbortableTask, TaskId, P], Coroutine[Any, Any, R]],
    ) -> Callable[Concatenate[AbortableTask, P], R]:
        @wraps(coro)
        def wrapper(task: AbortableTask, *args: P.args, **kwargs: P.kwargs) -> R:
            fastapi_app = get_fastapi_app(app)
            # NOTE: task.request is a thread local object, so we need to pass the id explicitly
            assert task.request.id is not None  # nosec

            async def run_task(task_id: TaskID) -> R:
                task_coro = asyncio.create_task(coro(task, task_id, *args, **kwargs))

                can_continue = True
                while can_continue:
                    if AbortableAsyncResult(task_id).is_aborted():
                        _logger.warning("Task %s was aborted by user.", task_id)
                        await cancel_wait_task(task_coro, max_delay=5)  # to constant
                        raise asyncio.CancelledError
                    if task_coro.done():
                        break

                    await asyncio.sleep(_DEFAULT_ABORT_TASK_TIMEOUT.total_seconds())

                return task_coro.result()

            return asyncio.run_coroutine_threadsafe(
                run_task(task.request.id),
                get_event_loop(fastapi_app),
            ).result()

        return wrapper

    return decorator


def _error_handling(
    max_retries: NonNegativeInt,
    delay_between_retries: timedelta,
    dont_autoretry_for: tuple[type[Exception], ...],
) -> Callable[
    [Callable[Concatenate[AbortableTask, P], R]],
    Callable[Concatenate[AbortableTask, P], R],
]:
    def decorator(
        func: Callable[Concatenate[AbortableTask, P], R],
    ) -> Callable[Concatenate[AbortableTask, P], R]:
        @wraps(func)
        def wrapper(task: AbortableTask, *args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(task, *args, **kwargs)
            except concurrent.futures.CancelledError as exc:
                _logger.warning("Task %s was cancelled", task.request.id)
                raise Ignore from exc
            except Exception as exc:
                if isinstance(exc, dont_autoretry_for):
                    _logger.debug("Not retrying for exception %s", type(exc).__name__)
                    # propagate without retry
                    raise encore_celery_transferrable_error(exc) from exc

                exc_type = type(exc).__name__
                exc_message = f"{exc}"
                _logger.exception(
                    "Task %s failed with exception: %s:%s",
                    task.request.id,
                    exc_type,
                    exc_message,
                )

                raise task.retry(
                    max_retries=max_retries,
                    countdown=delay_between_retries.total_seconds(),
                    exc=encore_celery_transferrable_error(exc),
                ) from exc

        return wrapper

    return decorator


@overload
def register_task(
    app: Celery,
    fn: Callable[Concatenate[AbortableTask, TaskId, P], Coroutine[Any, Any, R]],
    task_name: str | None = None,
    timeout: timedelta | None = _DEFAULT_TASK_TIMEOUT,
    max_retries: NonNegativeInt = _DEFAULT_MAX_RETRIES,
    delay_between_retries: timedelta = _DEFAULT_WAIT_BEFORE_RETRY,
    dont_autoretry_for: tuple[type[Exception], ...] = _DEFAULT_DONT_AUTORETRY_FOR,
) -> None: ...


@overload
def register_task(
    app: Celery,
    fn: Callable[Concatenate[AbortableTask, P], R],
    task_name: str | None = None,
    timeout: timedelta | None = _DEFAULT_TASK_TIMEOUT,
    max_retries: NonNegativeInt = _DEFAULT_MAX_RETRIES,
    delay_between_retries: timedelta = _DEFAULT_WAIT_BEFORE_RETRY,
    dont_autoretry_for: tuple[type[Exception], ...] = _DEFAULT_DONT_AUTORETRY_FOR,
) -> None: ...


def register_task(  # type: ignore[misc]
    app: Celery,
    fn: (
        Callable[Concatenate[AbortableTask, TaskId, P], Coroutine[Any, Any, R]]
        | Callable[Concatenate[AbortableTask, P], R]
    ),
    task_name: str | None = None,
    timeout: timedelta | None = _DEFAULT_TASK_TIMEOUT,
    max_retries: NonNegativeInt = _DEFAULT_MAX_RETRIES,
    delay_between_retries: timedelta = _DEFAULT_WAIT_BEFORE_RETRY,
    dont_autoretry_for: tuple[type[Exception], ...] = _DEFAULT_DONT_AUTORETRY_FOR,
) -> None:
    """Decorator to define a celery task with error handling and abortable support

    Keyword Arguments:
        task_name -- name of the function used in Celery (default: {None} will be generated automatically)
        timeout -- when None no timeout is enforced, task is allowed to run forever (default: {_DEFAULT_TASK_TIMEOUT})
        max_retries -- number of attempts in case of failuire before giving up (default: {_DEFAULT_MAX_RETRIES})
        delay_between_retries -- dealy between each attempt in case of error (default: {_DEFAULT_WAIT_BEFORE_RETRY})
        dont_autoretry_for -- exceptions that should not be retried when raised by the task
    """
    wrapped_fn: Callable[Concatenate[AbortableTask, P], R]
    if asyncio.iscoroutinefunction(fn):
        wrapped_fn = _async_task_wrapper(app)(fn)
    else:
        assert inspect.isfunction(fn)  # nosec
        wrapped_fn = fn

    wrapped_fn = _error_handling(
        max_retries=max_retries,
        delay_between_retries=delay_between_retries,
        dont_autoretry_for=dont_autoretry_for,
    )(wrapped_fn)

    app.task(
        name=task_name or fn.__name__,
        bind=True,
        base=AbortableTask,
        time_limit=None if timeout is None else timeout.total_seconds(),
    )(wrapped_fn)
