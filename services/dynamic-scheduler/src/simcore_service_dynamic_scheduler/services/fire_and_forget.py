from asyncio import Task
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.app_state import SingletonInAppStateMixin


class FireAndForgetCollection(SingletonInAppStateMixin):
    app_state_name: str = "fire_and_forget_collection"

    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self._tasks_collection: set[Task] = set()

    @property
    def tasks_collection(self) -> set[Task]:
        return self._tasks_collection


async def fire_and_forget_lifespan(app: FastAPI) -> AsyncIterator[State]:
    public_client = FireAndForgetCollection(app)
    public_client.set_to_app_state(app)

    yield {}

    public_client.pop_from_app_state(app)
