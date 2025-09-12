from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI
from fastapi_lifespan_manager import State

from . import _core, _event_scheduler, _store


def get_generic_scheduler_lifespans() -> (
    list[Callable[[FastAPI], AsyncIterator[State]]]
):
    return [_store.lifespan, _core.lifespan, _event_scheduler.lifespan]
