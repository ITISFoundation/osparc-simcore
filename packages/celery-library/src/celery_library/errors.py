import base64
import binascii
import logging
import pickle
import pickletools
import types
from collections.abc import Callable
from functools import wraps
from typing import Any, Final, cast

from celery.exceptions import (  # type: ignore[import-untyped]
    BackendError,
    CeleryError,
    OperationalError,
)
from common_library.error_codes import create_error_code
from common_library.errors_classes import OsparcErrorMixin
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

_logger = logging.getLogger(__name__)

# Marks the plain-text payload used when an exception cannot be pickled at all.
# ':' is not part of the base64 alphabet, so this prefix is unambiguous with
# respect to the (unprefixed, for backwards compatibility) base64 pickle payloads.
_PLAIN_TEXT_MARKER: Final[bytes] = b"t1:"

# a pickled global is built from two consecutive strings (module, qualname)
_PICKLE_GLOBAL_ARITY: Final[int] = 2


class _UnreconstructablePickleError(Exception):
    """Stand-in for a pickled exception that could not be reconstructed.

    Preserves the original type name (as the dynamic class name) and message (as the
    sole arg), so that error reporting (e.g. ``JobError.exc_type``/``exc_msg``) and
    string formatting stay useful instead of raising.
    """


def _standin_exception(type_name: str | None, message: str) -> Exception:
    class_name = (type_name or "Exception").rsplit(".", maxsplit=1)[-1] or "Exception"
    cls = types.new_class(class_name, (_UnreconstructablePickleError,), {})
    cls.__module__ = __name__
    return cast(Exception, cls(message))


def _describe_pickle_stream(payload: bytes) -> tuple[str | None, str]:
    """Best-effort recovery of ``(type name, message)`` from a pickle payload.

    Inspects the pickle opcodes without *executing* them, so it stays safe even for
    payloads that ``pickle.loads`` refuses to reconstruct.
    """
    module_name: str | None = None
    qualname: str | None = None
    message = ""

    try:
        ops = list(pickletools.genops(payload))
    except Exception:  # pylint: disable=broad-except
        _logger.debug("Cannot parse pickle stream", exc_info=True)
        ops = []

    string_ops: Final[frozenset[str]] = frozenset({"BINUNICODE", "SHORT_BINUNICODE"})
    pending_strings: list[str] = []
    after_global = False

    for op, arg, _pos in ops:
        if after_global:
            # first string operand after the exception's global is its message
            if isinstance(arg, str):
                message = arg
                break
            continue
        if op.name in string_ops and isinstance(arg, str):
            pending_strings.append(arg)
            if len(pending_strings) > _PICKLE_GLOBAL_ARITY:
                pending_strings.pop(0)
        elif op.name == "STACK_GLOBAL" and len(pending_strings) >= _PICKLE_GLOBAL_ARITY:
            # first STACK_GLOBAL constructs the pickled object itself (the exception);
            # later ones belong to objects nested in its __dict__
            module_name, qualname = pending_strings[-2], pending_strings[-1]
            after_global = True
            pending_strings.clear()
        elif op.name != "MEMOIZE":
            pending_strings.clear()

    if module_name and qualname:
        return f"{module_name}.{qualname}", message
    return qualname or module_name, message


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
    try:
        dumped = pickle.dumps(error)
    except Exception as exc:  # pylint: disable=broad-except
        # some exceptions cannot be pickled at all (e.g. broken __reduce__/__getstate__)
        # -- degrade to a plain-text description instead of crashing the error handler
        # NOTE: the OEC fingerprint deduplicates this log site; grep it in Loki to
        # find which exception types need first-class transferable-error handling
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                f"Cannot pickle {type(error).__name__}, transferring a text description instead",
                error=exc,
                error_code=create_error_code(exc),
                error_context={
                    "original_error_type": type(error).__name__,
                    "failed_picking_at": "encode_celery_transferable_error",
                },
                tip=(
                    "This exception type cannot be pickled, so consumers receive a text "
                    "description instead. Consider converting it to an OsparcErrorMixin "
                    "error (which defines __reduce__) before it reaches the task error handler."
                ),
            )
        )
        description = f"{type(error).__name__}: {error}"
        return TransferableCeleryError(_PLAIN_TEXT_MARKER + description.encode(errors="replace"))
    return TransferableCeleryError(base64.b64encode(dumped))


def decode_celery_transferable_error(error: TransferableCeleryError) -> Exception:
    """
    NOTE: exception safe
    """
    assert isinstance(error, TransferableCeleryError)  # nosec
    payload = error.args[0] if error.args else b""
    if isinstance(payload, str):
        payload = payload.encode()

    if payload.startswith(_PLAIN_TEXT_MARKER):
        text = payload.removeprefix(_PLAIN_TEXT_MARKER).decode(errors="replace")
        type_name, _, message = text.partition(": ")
        return _standin_exception(type_name or None, message or text)

    raw: bytes | None
    try:
        raw = base64.b64decode(payload)
    except (binascii.Error, ValueError):
        raw = None

    reconstruction_error: Exception | None = None
    if raw is not None:
        try:
            result: Exception = pickle.loads(raw)  # noqa: S301
            return result
        except Exception as exc:  # pylint: disable=broad-except
            # The payload pickled fine on the worker but cannot be reconstructed here
            # (e.g. httpx.HTTPStatusError.__init__ requires keyword-only request/response).
            # Degrade to a description extracted from the pickle stream so that callers
            # (get_job_result, webserver task APIs, __str__/__repr__) can still report
            # the original failure instead of raising a TypeError.
            reconstruction_error = exc

    try:
        type_name, message = _describe_pickle_stream(raw if raw is not None else payload)
    except Exception:  # pylint: disable=broad-except
        _logger.debug("Cannot describe transferable celery error", exc_info=True)
        type_name, message = None, ""

    if reconstruction_error is not None:
        try:
            # NOTE: the OEC fingerprint deduplicates this log site; grep it in Loki to
            # find which exception types need first-class transferable-error handling
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    "Cannot reconstruct transferable celery error, reporting a description instead",
                    error=reconstruction_error,
                    error_code=create_error_code(reconstruction_error),
                    error_context={
                        "original_error_type": type_name,
                        "failed_decoding_at": "decode_celery_transferable_error",
                    },
                    tip=(
                        "This exception type pickles but cannot be unpickled, so a stand-in "
                        "exception is reported instead. Consider converting it to an "
                        "OsparcErrorMixin error (which defines __reduce__) before it is "
                        "encoded as a transferable celery error."
                    ),
                )
            )
        except Exception:  # pylint: disable=broad-except
            # decoding must never raise, not even while logging about it
            _logger.warning("Cannot reconstruct transferable celery error (%s)", reconstruction_error)
    return _standin_exception(type_name, message)


class GroupSubmissionError(OsparcErrorMixin, Exception):
    msg_template = "Unable to submit group {group_name} with key '{group_key}'"


class TaskSubmissionError(OsparcErrorMixin, Exception):
    msg_template = "Unable to submit task {task_name} with key '{task_key}' and params {task_params}"


class TaskOrGroupNotFoundError(OsparcErrorMixin, Exception):
    msg_template = "Task or group with uuid '{task_uuid}' and owner_metadata '{owner_metadata}' was not found"


class TaskManagerError(OsparcErrorMixin, Exception):
    msg_template = "An internal error occurred"


_TASK_MANAGER_ERRORS: Final[tuple[type[Exception], ...]] = (
    BackendError,
    CeleryError,
    OperationalError,
    RedisConnectionError,
    RedisTimeoutError,
)


def handle_celery_errors[F: Callable[..., Any]](func: F) -> F:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except _TASK_MANAGER_ERRORS as exc:
            raise TaskManagerError from exc

    return wrapper  # type: ignore[return-value]
