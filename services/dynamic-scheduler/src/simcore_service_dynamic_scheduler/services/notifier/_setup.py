from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

from . import _notifier, _socketio


def _get_notifier_lifespans() -> list[Callable[[FastAPI], AsyncIterator[State]]]:
    return [_socketio.lifespan, _notifier.lifespan]


def configure_notifier(app_lifespan: LifespanManager[FastAPI]) -> None:
    for lifespan in _get_notifier_lifespans():
        app_lifespan.add(lifespan)
