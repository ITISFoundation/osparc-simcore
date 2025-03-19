import asyncio
import logging
import traceback
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from celery import (  # type: ignore[import-untyped]
    Celery,
    Task,
)
from celery.contrib.abortable import AbortableTask  # type: ignore[import-untyped]
from celery.exceptions import Ignore  # type: ignore[import-untyped]

from . import get_event_loop
from .models import TaskError, TaskState
from .utils import get_fastapi_app

_logger = logging.getLogger(__name__)


def error_handling(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(task: Task, *args: Any, **kwargs: Any) -> Any:
        try:
            return func(task, *args, **kwargs)
        except Exception as exc:
            exc_type = type(exc).__name__
            exc_message = f"{exc}"
            exc_traceback = traceback.format_exc().split("\n")

            _logger.exception(
                "Task %s failed with exception: %s",
                task.request.id,
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
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, R]]:
    def decorator(coro: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:
        @wraps(coro)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            fastapi_app = get_fastapi_app(app)
            return asyncio.run_coroutine_threadsafe(
                coro(*args, **kwargs), get_event_loop(fastapi_app)
            ).result()

        return wrapper

    return decorator


def define_task(app: Celery, fn: Callable, task_name: str | None = None):
    wrapped_fn = error_handling(fn)
    if asyncio.iscoroutinefunction(fn):
        wrapped_fn = _async_task_wrapper(app)(fn)

    app.task(
        name=task_name or fn.__name__,
        bind=True,
        base=AbortableTask,
    )(wrapped_fn)
