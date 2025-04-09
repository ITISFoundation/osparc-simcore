from collections.abc import AsyncIterator
from typing import Protocol

from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State


class LifespanError(OsparcErrorMixin, RuntimeError): ...


class LifespanOnStartupError(LifespanError):
    msg_template = "Failed during startup of {module}"


class LifespanOnShutdownError(LifespanError):
    msg_template = "Failed during shutdown of {module}"


class LifespanGenerator(Protocol):
    def __call__(self, app: FastAPI) -> AsyncIterator["State"]: ...


def combine_lifespans(*generators: LifespanGenerator) -> LifespanManager:

    manager = LifespanManager()

    for generator in generators:
        manager.add(generator)

    return manager
