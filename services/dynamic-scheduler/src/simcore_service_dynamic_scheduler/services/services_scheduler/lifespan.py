from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State


async def services_scheduler_lifespan(app: FastAPI) -> AsyncIterator[State]:
    # Placeholder: start worker pool + wakeup consumer + poll loop
    _ = app
    yield {}
