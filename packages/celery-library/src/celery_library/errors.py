import base64
import pickle
from collections.abc import Callable
from functools import wraps
from typing import Any

from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from common_library.errors_classes import OsparcErrorMixin


class TransferableCeleryError(Exception):
    def __repr__(self) -> str:
        exception = decode_celery_transferable_error(self)
        return f"{self.__class__.__name__}({exception.__class__.__name__}({exception}))"

    def __str__(self) -> str:
        return f"{decode_celery_transferable_error(self)}"


def encode_celery_transferable_error(error: Exception) -> TransferableCeleryError:
    # NOTE: Celery modifies exceptions during serialization, which can cause
    # the original error context to be lost. This mechanism ensures the same
    # error can be recreated on the caller side exactly as it was raised here.
    return TransferableCeleryError(base64.b64encode(pickle.dumps(error)))


def decode_celery_transferable_error(error: TransferableCeleryError) -> Exception:
    assert isinstance(error, TransferableCeleryError)  # nosec
    result: Exception = pickle.loads(base64.b64decode(error.args[0]))  # noqa: S301
    return result


class GroupSubmissionError(OsparcErrorMixin, Exception):
    msg_template = "Unable to submit group {group_name} with id '{task_id}'"


class TaskSubmissionError(OsparcErrorMixin, Exception):
    msg_template = "Unable to submit task {task_name} with id '{task_id}' and params {task_params}"


class TaskNotFoundError(OsparcErrorMixin, Exception):
    msg_template = "Task with id '{task_id}' was not found"


class TaskManagerError(OsparcErrorMixin, Exception):
    msg_template = "An internal error occurred"


def handle_celery_errors[F: Callable[..., Any]](func: F) -> F:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except CeleryError as exc:
            raise TaskManagerError from exc

    return wrapper  # type: ignore[return-value]
