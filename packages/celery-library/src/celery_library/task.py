import asyncio
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
from common_library.async_tools import cancel_and_shielded_wait
from pydantic import NonNegativeInt
from servicelib.celery.models import TaskID

from .errors import encode_celery_transferrable_error
from .utils import get_app_server

_logger = logging.getLogger(__name__)

_DEFAULT_TASK_TIMEOUT: Final[timedelta | None] = None
_DEFAULT_MAX_RETRIES: Final[NonNegativeInt] = 3
_DEFAULT_WAIT_BEFORE_RETRY: Final[timedelta] = timedelta(seconds=5)
_DEFAULT_DONT_AUTORETRY_FOR: Final[tuple[type[Exception], ...]] = ()
_DEFAULT_ABORT_TASK_TIMEOUT: Final[timedelta] = timedelta(seconds=1)
_DEFAULT_CANCEL_TASK_TIMEOUT: Final[timedelta] = timedelta(seconds=5)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


class TaskAbortedError(Exception): ...


def _async_task_wrapper(
    app: Celery,
) -> Callable[
    [Callable[Concatenate[AbortableTask, P], Coroutine[Any, Any, R]]],
    Callable[Concatenate[AbortableTask, P], R],
]:
    def decorator(
        coro: Callable[Concatenate[AbortableTask, P], Coroutine[Any, Any, R]],
    ) -> Callable[Concatenate[AbortableTask, P], R]:
        @wraps(coro)
        def wrapper(task: AbortableTask, *args: P.args, **kwargs: P.kwargs) -> R:
            app_server = get_app_server(app)
            # NOTE: task.request is a thread local object, so we need to pass the id explicitly
            assert task.request.id is not None  # nosec

            async def run_task(task_id: TaskID) -> R:
                try:
                    async with asyncio.TaskGroup() as tg:
                        main_task = tg.create_task(
                            coro(task, *args, **kwargs),
                        )

                        async def abort_monitor():
                            abortable_result = AbortableAsyncResult(task_id, app=app)
                            while not main_task.done():
                                if abortable_result.is_aborted():
                                    await cancel_and_shielded_wait(
                                        main_task,
                                        max_delay=_DEFAULT_CANCEL_TASK_TIMEOUT.total_seconds(),
                                    )
                                    AbortableAsyncResult(task_id, app=app).forget()
                                    raise TaskAbortedError
                                await asyncio.sleep(
                                    _DEFAULT_ABORT_TASK_TIMEOUT.total_seconds()
                                )

                        tg.create_task(abort_monitor())

                    return main_task.result()
                except BaseExceptionGroup as eg:
                    task_aborted_errors, other_errors = eg.split(TaskAbortedError)

                    if task_aborted_errors:
                        assert task_aborted_errors is not None  # nosec
                        assert len(task_aborted_errors.exceptions) == 1  # nosec
                        raise task_aborted_errors.exceptions[0] from eg

                    assert other_errors is not None  # nosec
                    assert len(other_errors.exceptions) == 1  # nosec
                    raise other_errors.exceptions[0] from eg

            return asyncio.run_coroutine_threadsafe(
                run_task(task.request.id),
                app_server.event_loop,
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
            except TaskAbortedError as exc:
                _logger.warning("Task %s was cancelled", task.request.id)
                raise Ignore from exc
            except Exception as exc:
                if isinstance(exc, dont_autoretry_for):
                    _logger.debug("Not retrying for exception %s", type(exc).__name__)
                    # propagate without retry
                    raise encode_celery_transferrable_error(exc) from exc

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
                    exc=encode_celery_transferrable_error(exc),
                ) from exc

        return wrapper

    return decorator


@overload
def register_task(
    app: Celery,
    fn: Callable[Concatenate[AbortableTask, TaskID, P], Coroutine[Any, Any, R]],
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
        Callable[Concatenate[AbortableTask, TaskID, P], Coroutine[Any, Any, R]]
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
        pydantic=True,
    )(wrapped_fn)
