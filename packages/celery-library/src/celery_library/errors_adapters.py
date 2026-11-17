# Exceptions that cannot cross a celery task boundary as-is (they pickle but never
# unpickle, or fail pickling altogether) are adapted to a serializable wire error
# at encode time and restored on the consumer side at decode time. Adapters are
# registered per exact exception type, so this library stays free of third-party
# imports: the service that owns the problematic exception registers its own
# adapter at startup. Registration is process-local, and both sides need it only
# for full restoration -- an unregistered consumer simply receives the wire error,
# which is still serializable and reportable.

import logging
from collections.abc import Callable
from typing import NamedTuple

from servicelib.logging_utils import log_catch

_logger = logging.getLogger(__name__)

type ToWireCallable = Callable[[Exception], Exception]
type FromWireCallable = Callable[[Exception], Exception]


class ErrorAdapter(NamedTuple):
    wire_type: type[Exception]
    to_wire: ToWireCallable
    from_wire: FromWireCallable


to_wire_adapters: dict[type[Exception], ErrorAdapter] = {}
from_wire_adapters: dict[type[Exception], FromWireCallable] = {}


def register_transferable_error_adapter(
    *,
    original_type: type[Exception],
    wire_type: type[Exception],
    to_wire: ToWireCallable,
    from_wire: FromWireCallable,
) -> None:
    """Register a two-way adapter for exceptions of ``original_type``.

    ``to_wire`` runs on the worker at encode time, while the original exception is
    fully intact, and must return an error that survives pickling (e.g. an
    OsparcErrorMixin subclass, whose __reduce__ round-trips). ``from_wire`` runs on
    the consumer at decode time to rebuild the original error from the wire one.
    """
    to_wire_adapters[original_type] = ErrorAdapter(wire_type=wire_type, to_wire=to_wire, from_wire=from_wire)
    from_wire_adapters[wire_type] = from_wire


def restore_original_error(wire_error: Exception) -> Exception:
    """Rebuild the original error from a wire error, when an adapter is registered.

    The wire error is always returned as-is if no adapter is registered or if the
    adapter fails, since it is itself serializable and reportable.
    """
    if (from_wire := from_wire_adapters.get(type(wire_error))) is None:
        return wire_error
    # decoding must never raise: if the adapter fails, the wire error below is
    # reported as-is, since it is itself serializable and reportable
    with log_catch(_logger, reraise=False):
        return from_wire(wire_error)
    return wire_error
