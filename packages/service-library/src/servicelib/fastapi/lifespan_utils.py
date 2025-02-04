from collections.abc import AsyncIterator
from typing import Protocol

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State


class LifespanGenerator(Protocol):
    def __call__(self, app: FastAPI) -> AsyncIterator["State"]:
        ...


def combine_lifespans(*generators: LifespanGenerator) -> LifespanManager:

    manager = LifespanManager()

    for generator in generators:
        manager.add(generator)

    return manager
