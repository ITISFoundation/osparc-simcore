import contextlib
from collections.abc import Iterator
from typing import Final

from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from fastapi_lifespan_manager import State

from ..logging_utils import log_context


class LifespanError(OsparcErrorMixin, RuntimeError): ...


class LifespanOnStartupError(LifespanError):
    msg_template = "Failed during startup of {lifespan_name}"


class LifespanOnShutdownError(LifespanError):
    msg_template = "Failed during shutdown of {lifespan_name}"


class LifespanAlreadyCalledError(LifespanError):
    msg_template = "The lifespan '{lifespan_name}' has already been called."


class LifespanExpectedCalledError(LifespanError):
    msg_template = "The lifespan '{lifespan_name}' was not called. Ensure it is properly configured and invoked."


_CALLED_LIFESPANS_KEY: Final[str] = "_CALLED_LIFESPANS"


def is_lifespan_called(state: State, lifespan_name: str) -> bool:
    # NOTE: This assert is meant to catch a common mistake:
    # The `lifespan` function should accept up to two *optional* positional arguments: (app: FastAPI, state: State).
    # Valid signatures include: `()`, `(app)`, `(app, state)`, or even `(_, state)`.
    # It's easy to accidentally swap or misplace these arguments.
    assert not isinstance(  # nosec
        state,  # type: ignore[unreachable]
        FastAPI,
    ), "Did you swap arguments? `lifespan(app, state)` expects (app: FastAPI, state: State)"

    called_lifespans = state.get(_CALLED_LIFESPANS_KEY, set())
    return lifespan_name in called_lifespans


def mark_lifespace_called(state: State, lifespan_name: str) -> State:
    """Validates if a lifespan has already been called and records it in the state.
    Raises LifespanAlreadyCalledError if the lifespan has already been called.
    """
    if is_lifespan_called(state, lifespan_name):
        raise LifespanAlreadyCalledError(lifespan_name=lifespan_name)

    called_lifespans = state.get(_CALLED_LIFESPANS_KEY, set())
    called_lifespans.add(lifespan_name)
    return {_CALLED_LIFESPANS_KEY: called_lifespans}


def ensure_lifespan_called(state: State, lifespan_name: str) -> None:
    """Ensures that a lifespan has been called.
    Raises LifespanNotCalledError if the lifespan has not been called.
    """
    if not is_lifespan_called(state, lifespan_name):
        raise LifespanExpectedCalledError(lifespan_name=lifespan_name)


@contextlib.contextmanager
def lifespan_context(
    logger, level, lifespan_name: str, state: State
) -> Iterator[State]:
    """Helper context manager to log lifespan event and mark lifespan as called."""

    with log_context(logger, level, lifespan_name):
        # Check if lifespan has already been called
        called_state = mark_lifespace_called(state, lifespan_name)

        yield called_state
