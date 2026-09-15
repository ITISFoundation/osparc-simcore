import base64
import binascii
import logging
import pickle
import pickletools
import types
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import wraps
from typing import Any, Final, NamedTuple

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

_logger = logging.getLogger(__name__)

# Marks the plain-text payload used when an exception cannot be pickled at all.
# ':' is not part of the base64 alphabet, so this prefix is unambiguous with
# respect to the (unprefixed, for backwards compatibility) base64 pickle payloads.
_PLAIN_TEXT_MARKER: Final[bytes] = b"t1:"

# a pickled global is built from two consecutive strings (module, qualname)
_PICKLE_GLOBAL_ARITY: Final[int] = 2


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
            # reporting must not break the transfer either (e.g. a broken __str__)
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


def _describe_pickle_stream(payload: bytes) -> tuple[str | None, str]:
    """Best-effort recovery of ``(type name, message)`` from a pickle payload.

    Inspects the pickle opcodes without *executing* them, so it stays safe even for
    payloads that ``pickle.loads`` refuses to reconstruct.
    """
    module_name: str | None = None
    qualname: str | None = None
    message = ""

    ops: list[tuple[pickletools.OpcodeInfo, Any, Any]] = []
    with log_catch(_logger, reraise=False):
        ops = list(pickletools.genops(payload))

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


# Exceptions that cannot cross a celery task boundary as-is (they pickle but never
# unpickle, or fail pickling altogether) are adapted to a serializable wire error
# at encode time and restored on the consumer side at decode time. Adapters are
# registered per exact exception type, so this library stays free of third-party
# imports: the service that owns the problematic exception registers its own
# adapter at startup. Registration is process-local, and both sides need it only
# for full restoration -- an unregistered consumer simply receives the wire error,
# which is still serializable and reportable.
type _ToWireCallable = Callable[[Exception], Exception]
type _FromWireCallable = Callable[[Exception], Exception]


class _ErrorAdapter(NamedTuple):
    wire_type: type[Exception]
    to_wire: _ToWireCallable
    from_wire: _FromWireCallable


_to_wire_adapters: dict[type[Exception], _ErrorAdapter] = {}
_from_wire_adapter: dict[type[Exception], _FromWireCallable] = {}


def register_transferable_error_adapter(
    *,
    original_type: type[Exception],
    wire_type: type[Exception],
    to_wire: _ToWireCallable,
    from_wire: _FromWireCallable,
) -> None:
    """Register a two-way adapter for exceptions of ``original_type``.

    ``to_wire`` runs on the worker at encode time, while the original exception is
    fully intact, and must return an error that survives pickling (e.g. an
    OsparcErrorMixin subclass, whose __reduce__ round-trips). ``from_wire`` runs on
    the consumer at decode time to rebuild the original error from the wire one.
    """
    _to_wire_adapters[original_type] = _ErrorAdapter(wire_type=wire_type, to_wire=to_wire, from_wire=from_wire)
    _from_wire_adapter[wire_type] = from_wire


def encode_celery_transferable_error(error: Exception) -> TransferableCeleryError:
    # NOTE: Celery modifies exceptions during serialization, which can cause
    # the original error context to be lost. This mechanism ensures the same
    # error can be recreated on the caller side exactly as it was raised here.
    if (adapter := _to_wire_adapters.get(type(error))) is not None:
        try:
            error = adapter.to_wire(error)
        except Exception:  # pylint: disable=broad-except
            # a broken adapter must not crash the error handler
            _logger.warning(
                "Adapter for %s failed, transferring the original error instead",
                type(error).__name__,
                exc_info=True,
            )
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


def _restore_original_error(wire_error: Exception) -> Exception:
    """Rebuild the original error from a wire error, when an adapter is registered.

    The wire error is always returned as-is if no adapter is registered or if the
    adapter fails, since it is itself serializable and reportable.
    """
    if (from_wire := _from_wire_adapter.get(type(wire_error))) is None:
        return wire_error
    try:
        return from_wire(wire_error)
    except Exception:  # pylint: disable=broad-except
        # decoding must never raise -- fall back to the wire error
        _logger.warning(
            "Adapter to restore %s failed, reporting the wire error instead",
            type(wire_error).__name__,
            exc_info=True,
        )
        return wire_error


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
    except (binascii.Error, ValueError):
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
            return _restore_original_error(result)

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
