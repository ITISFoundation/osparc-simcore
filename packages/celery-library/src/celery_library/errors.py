import base64
import logging
import pickle
import pickletools
import types
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import wraps
from typing import Any, Final

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
from servicelib.logging_utils import log_catch

from .errors_adapters import (
    restore_original_error,
    to_wire_adapters,
)

_logger = logging.getLogger(__name__)

# Marks the plain-text payload used when an exception cannot be pickled at all.
# ':' is not part of the base64 alphabet, so this prefix is unambiguous with
# respect to the (unprefixed, for backwards compatibility) base64 pickle payloads.
_PLAIN_TEXT_MARKER: Final[bytes] = b"t1:"

# a pickled global is built from two consecutive strings (module, qualname)
_PICKLE_GLOBAL_ARITY: Final[int] = 2

# pickle opcodes that carry a string operand
_STRING_OPS: Final[frozenset[str]] = frozenset({"BINUNICODE", "SHORT_BINUNICODE"})


@contextmanager
def _log_degradation(
    *,
    message: str,
    context: dict[str, Any],
    tip: str,
    fallback_prefix: str,
) -> Generator[None]:
    """Guard for degradation paths that must never raise.

    The guarded ``with`` body runs normally; if it raises, the error is logged with
    troubleshooting OEC kwargs (never re-raised) and the remainder of the block is
    skipped, so the caller builds its fallback value instead.

    NOTE: the OEC fingerprint deduplicates this log site; grep it in the log
    aggregator to find which exception types need first-class transferable-error
    handling.
    """
    try:
        yield
    except Exception as exc:  # pylint: disable=broad-except
        try:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    message,
                    error=exc,
                    error_code=create_error_code(exc),
                    error_context=context,
                    tip=tip,
                )
            )
        except Exception:  # pylint: disable=broad-except
            # reporting must not break the transfer either (e.g. a broken __str__).
            # warning-level on purpose: this should be near-impossible, so hitting
            # it means the fallback itself is buggy and the consumer loses all
            # information about the original failure
            _logger.warning("%s: %s", fallback_prefix, exc)


class _UnreconstructablePickleError(Exception):
    """Stand-in for a pickled exception that could not be reconstructed.

    Preserves the original type name (as the dynamic class name) and message (as the
    sole arg), so consumers can still report the failure's type and message and
    format it as a string without raising.

    Derived from ``Exception`` on purpose: it stands in for an *arbitrary* foreign
    exception, so a more specific base (e.g. ``RuntimeError``) would mislabel the
    error being reported.
    """


def _standin_exception(type_name: str | None, message: str) -> Exception:
    class_name = (type_name or "Exception").rsplit(".", maxsplit=1)[-1] or "Exception"
    cls: type[Exception] = types.new_class(class_name, (_UnreconstructablePickleError,), {})
    cls.__module__ = __name__
    return cls(message)


type _PickleOp = tuple[pickletools.OpcodeInfo, Any, Any]


def _find_exception_global(ops: list[_PickleOp]) -> tuple[int, str, str] | None:
    """Locate the ``STACK_GLOBAL`` that rebuilds the pickled exception itself.

    Returns ``(index, module name, qualname)`` of the first ``STACK_GLOBAL`` fed by
    two consecutive string operands; later globals belong to objects nested in the
    exception's ``__dict__`` and are ignored. ``None`` if the stream has no global.
    """
    pending_strings: list[str] = []
    for index, (op, arg, _pos) in enumerate(ops):
        if op.name in _STRING_OPS and isinstance(arg, str):
            pending_strings.append(arg)
            if len(pending_strings) > _PICKLE_GLOBAL_ARITY:
                pending_strings.pop(0)
        elif op.name == "STACK_GLOBAL" and len(pending_strings) >= _PICKLE_GLOBAL_ARITY:
            return index, pending_strings[-2], pending_strings[-1]
        elif op.name != "MEMOIZE":
            pending_strings.clear()
    return None


def _find_exception_message(ops: list[_PickleOp], after_index: int) -> str:
    """Return the first string operand after ``after_index`` (the exception's message)."""
    for _op, arg, _pos in ops[after_index + 1 :]:
        if isinstance(arg, str):
            return arg
    return ""


def _describe_pickle_stream(payload: bytes) -> tuple[str | None, str]:
    """Best-effort recovery of ``(type name, message)`` from a pickle payload.

    Inspects the pickle opcodes without *executing* them, so it stays safe even for
    payloads that ``pickle.loads`` refuses to reconstruct.
    """
    ops: list[_PickleOp] = []
    with log_catch(_logger, reraise=False):
        ops = list(pickletools.genops(payload))

    if (found := _find_exception_global(ops)) is None:
        return None, ""

    global_index, module_name, qualname = found
    message = _find_exception_message(ops, global_index)
    return f"{module_name}.{qualname}", message


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
    if (adapter := to_wire_adapters.get(type(error))) is not None:
        # a broken adapter must not crash the error handler: on failure the
        # original error is kept and transferred as-is
        with log_catch(_logger, reraise=False):
            error = adapter.to_wire(error)
    # some exceptions cannot be pickled at all (e.g. broken __reduce__/__getstate__)
    # -- degrade to a plain-text description instead of crashing the error handler
    with _log_degradation(
        message=f"Cannot pickle {type(error).__name__}, transferring a text description instead",
        context={
            "original_error_type": type(error).__name__,
            "failed_pickling_at": "encode_celery_transferable_error",
        },
        tip=(
            "This exception type cannot be pickled, so consumers receive a text "
            "description instead. Consider converting it to an OsparcErrorMixin "
            "error (which defines __reduce__) before it reaches the task error handler."
        ),
        fallback_prefix=f"Cannot pickle {type(error).__name__}",
    ):
        dumped = pickle.dumps(error)
        return TransferableCeleryError(base64.b64encode(dumped))
    try:
        description = f"{type(error).__name__}: {error}"
    except Exception:  # pylint: disable=broad-except
        # the original may not even survive string formatting
        description = type(error).__name__
    return TransferableCeleryError(_PLAIN_TEXT_MARKER + description.encode(errors="replace"))


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
        text_type_name, _, text_message = text.partition(": ")
        return _standin_exception(text_type_name or None, text_message or text)

    raw: bytes | None
    try:
        raw = base64.b64decode(payload)
    except ValueError:  # includes binascii.Error: not a base64 payload
        raw = None

    reconstruction_error: Exception | None = None
    if raw is not None:
        try:
            result: Exception = pickle.loads(raw)  # noqa: S301
        except Exception as exc:  # pylint: disable=broad-except
            # The payload pickled fine on the worker but cannot be reconstructed here
            # (e.g. httpx.HTTPStatusError.__init__ requires keyword-only request/response).
            # Degrade to a description extracted from the pickle stream so that callers
            # (get_job_result, webserver task APIs, __str__/__repr__) can still report
            # the original failure instead of raising a TypeError.
            reconstruction_error = exc
        else:
            return restore_original_error(result)

    type_name: str | None = None
    message = ""
    with log_catch(_logger, reraise=False):
        type_name, message = _describe_pickle_stream(raw if raw is not None else payload)

    if reconstruction_error is not None:
        with _log_degradation(
            message="Cannot reconstruct transferable celery error, reporting a description instead",
            context={
                "original_error_type": type_name,
                "failed_decoding_at": "decode_celery_transferable_error",
            },
            tip=(
                "This exception type pickles but cannot be unpickled, so a stand-in "
                "exception is reported instead. Consider converting it to an "
                "OsparcErrorMixin error (which defines __reduce__) before it is "
                "encoded as a transferable celery error."
            ),
            fallback_prefix="Cannot reconstruct transferable celery error",
        ):
            raise reconstruction_error

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
