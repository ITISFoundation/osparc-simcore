from typing import Final

from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from fastapi_lifespan_manager import State


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
    assert not isinstance(  # nosec
        state, FastAPI
    ), "TIP: lifespan func has (app, state) positional arguments"

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
