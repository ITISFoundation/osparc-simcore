import contextlib
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Final

from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from ..logging_utils import log_context

type Lifespan = Callable[[FastAPI], AsyncIterator[None]]
type PublisherLifespan = Callable[[FastAPI, State], AsyncIterator[State]]


def create_publisher_lifespan(state_key: str, app_state_attr: str) -> PublisherLifespan:
    """Creates a generic publisher lifespan that reads a value from the lifespan
    state and stores it on app.state under the given attribute name.

    Raises:
        KeyError: If `state_key` is not present in the lifespan state.
    """

    async def _publisher_lifespan(app: FastAPI, state: State) -> AsyncIterator[State]:
        if state_key not in state:
            msg = f"Expected lifespan state key '{state_key}' not found"
            raise KeyError(msg)
        setattr(app.state, app_state_attr, state[state_key])
        yield {}

    return _publisher_lifespan


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
        state, FastAPI
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
def lifespan_context(logger, level, lifespan_name: str, state: State) -> Iterator[State]:
    """Helper context manager to log lifespan event and mark lifespan as called."""

    with log_context(logger, level, lifespan_name):
        # Check if lifespan has already been called
        called_state = mark_lifespace_called(state, lifespan_name)

        yield called_state


def _make_starting_shutdown_complete_lifespan(
    starting_banner: str,
    shutdown_complete_banner: str,
) -> Lifespan:
    # NOTE: uses print because startup/shutdown messages should be emitted even without logging
    async def _starting_shutdown_complete_lifespan(_: FastAPI) -> AsyncIterator[State]:
        print(starting_banner, flush=True)  # noqa: T201
        yield {}
        print(shutdown_complete_banner, flush=True)  # noqa: T201

    return _starting_shutdown_complete_lifespan


def _make_started_shutting_down_lifespan(
    started_banner: str,
    shutting_down_banner: str,
) -> Lifespan:
    async def _started_shutting_down_lifespan(_: FastAPI) -> AsyncIterator[State]:
        print(started_banner, flush=True)  # noqa: T201
        yield {}
        print(shutting_down_banner, flush=True)  # noqa: T201

    return _started_shutting_down_lifespan


@contextlib.contextmanager
def configure_app_lifespan(
    *,
    logging_lifespan: Lifespan | None = None,
    starting_banner: str,
    started_banner: str,
    shutting_down_banner: str = "Shutting down service...",
    shutdown_complete_banner: str = "Service shut down.",
) -> Iterator[LifespanManager]:
    """Creates and configures a LifespanManager with enforced ordering.

    Startup order:  starting/shutdown-complete → logging → [plugins yielded to caller] → started/shutting-down
    Shutdown order: started/shutting-down → [plugins] → logging → starting/shutdown-complete

    Yields:
        LifespanManager to pass as `lifespan=` to FastAPI and to register plugin lifespans.
    """
    app_lifespan = LifespanManager()

    # Added first → prints on startup before anything else and on shutdown as absolute last message
    app_lifespan.add(
        _make_starting_shutdown_complete_lifespan(
            starting_banner,
            shutdown_complete_banner,
        )
    )
    if logging_lifespan:
        app_lifespan.add(logging_lifespan)

    yield app_lifespan

    # Added last → runs last on startup, first on shutdown
    app_lifespan.add(_make_started_shutting_down_lifespan(started_banner, shutting_down_banner))
