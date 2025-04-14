from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from . import _notifier, _socketio


def get_notifier_lifespans() -> list[Callable[[FastAPI], AsyncIterator[State]]]:
    return [_socketio.lifespan, _notifier.lifespan]
