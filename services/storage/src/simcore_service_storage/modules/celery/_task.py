import asyncio
import inspect
import logging
import traceback
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar, overload

from celery import Celery  # type: ignore[import-untyped]
from celery.contrib.abortable import AbortableTask  # type: ignore[import-untyped]
from celery.exceptions import Ignore  # type: ignore[import-untyped]

from . import get_event_loop
from .models import TaskError, TaskId, TaskState
from .utils import get_fastapi_app

_logger = logging.getLogger(__name__)


def error_handling(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(task: AbortableTask, *args: Any, **kwargs: Any) -> Any:
        try:
            return func(task, *args, **kwargs)
        except Exception as exc:
            exc_type = type(exc).__name__
            exc_message = f"{exc}"
            exc_traceback = traceback.format_exc().split("\n")

            _logger.exception(
                "Task %s failed with exception: %s:%s",
                task.request.id,
                exc_type,
                exc_message,
            )

            task.update_state(
                state=TaskState.ERROR.upper(),
                meta=TaskError(
                    exc_type=exc_type,
                    exc_msg=exc_message,
                ).model_dump(mode="json"),
                traceback=exc_traceback,
            )
            raise Ignore from exc  # ignore doing state updates

    return wrapper


T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


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
            _logger.debug("task id: %s", task.request.id)
            # NOTE: task.request is a thread local object, so we need to pass the id explicitly
            assert task.request.id is not None  # nosec
            return asyncio.run_coroutine_threadsafe(
                coro(task, task.request.id, *args, **kwargs),
                get_event_loop(fastapi_app),
            ).result()

        return wrapper

    return decorator


@overload
def define_task(
    app: Celery,
    fn: Callable[Concatenate[AbortableTask, TaskId, P], Coroutine[Any, Any, R]],
    task_name: str | None = None,
    task_queue: str | None = None,
) -> None: ...


@overload
def define_task(
    app: Celery,
    fn: Callable[Concatenate[AbortableTask, P], R],
    task_name: str | None = None,
    task_queue: str | None = None,
) -> None: ...


def define_task(  # type: ignore[misc]
    app: Celery,
    fn: (
        Callable[Concatenate[AbortableTask, TaskId, P], Coroutine[Any, Any, R]]
        | Callable[Concatenate[AbortableTask, P], R]
    ),
    task_name: str | None = None,
    task_queue: str | None = None,
) -> None:
    """Decorator to define a celery task with error handling and abortable support"""
    wrapped_fn: Callable[Concatenate[AbortableTask, P], R]
    if asyncio.iscoroutinefunction(fn):
        wrapped_fn = _async_task_wrapper(app)(fn)
    else:
        assert inspect.isfunction(fn)  # nosec
        wrapped_fn = fn

    wrapped_fn = error_handling(wrapped_fn)
    app.task(
        name=task_name or fn.__name__,
        bind=True,
        base=AbortableTask,
        queue=task_queue,
    )(wrapped_fn)
