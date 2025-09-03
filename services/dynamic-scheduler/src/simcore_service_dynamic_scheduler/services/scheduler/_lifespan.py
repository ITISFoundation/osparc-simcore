from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State


async def scheduler_lifespan(app: FastAPI) -> AsyncIterator[State]:
    # setup
    yield {}
    # teardown
