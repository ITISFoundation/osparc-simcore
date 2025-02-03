from collections.abc import AsyncIterator, Callable
from typing import TypeAlias

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State

SetupGenerator: TypeAlias = Callable[[FastAPI], AsyncIterator[State]]


def combine_setups(*generators: SetupGenerator) -> LifespanManager:

    manager = LifespanManager()

    for generator in generators:
        manager.add(generator)

    return manager
