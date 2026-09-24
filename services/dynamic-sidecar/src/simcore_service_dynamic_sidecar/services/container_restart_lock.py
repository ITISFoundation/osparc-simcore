from asyncio import Lock
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager


async def _container_restart_lock_lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.container_restart_lock = Lock()
    yield


def configure_container_restart_lock(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_container_restart_lock_lifespan)


def get_container_restart_lock(app: FastAPI) -> Lock:
    container_restart_lock: Lock = app.state.container_restart_lock
    return container_restart_lock
