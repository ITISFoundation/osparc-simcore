from collections.abc import Callable
from functools import wraps
import logging
import traceback

from celery import Celery, Task
from celery.exceptions import Ignore
from celery.contrib.abortable import AbortableTask
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from .models import TaskError

_logger = logging.getLogger(__name__)


def create_app(celery_settings: CelerySettings) -> Celery:
    assert celery_settings

    app = Celery(
        broker=celery_settings.CELERY_RABBIT_BROKER.dsn,
        backend=celery_settings.CELERY_REDIS_RESULT_BACKEND.build_redis_dsn(
            RedisDatabase.CELERY_TASKS,
        ),
    )
    app.conf.result_expires = celery_settings.CELERY_RESULT_EXPIRES
    app.conf.result_extended = True  # original args are included in the results
    app.conf.result_serializer = "json"
    app.conf.task_track_started = True
    return app


def error_handling(func: Callable):
    @wraps(func)
    def wrapper(task: Task, *args, **kwargs):
        try:
            return func(task, *args, **kwargs)
        except Exception as exc:
            exc_type = type(exc).__name__
            exc_message = f"{exc}"
            exc_traceback = traceback.format_exc().split('\n')

            _logger.exception(
                "Task %s failed with exception: %s",
                task.request.id,
                exc_message,
            )

            task.update_state(
                state="ERROR",
                meta=TaskError(
                    exc_type=exc_type,
                    exc_msg=exc_message,
                ).model_dump(mode="json"),
                traceback=exc_traceback
            )
            raise Ignore from exc
    return wrapper


def define_task(app: Celery, fn: Callable, task_name: str | None = None):
    app.task(
        name=task_name or fn.__name__,
        bind=True,
        base=AbortableTask,
    )(error_handling(fn))
