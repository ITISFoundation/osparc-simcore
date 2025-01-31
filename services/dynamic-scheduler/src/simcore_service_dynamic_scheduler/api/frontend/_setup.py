from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import nicegui
from fastapi import FastAPI

from ...core.settings import ApplicationSettings
from ._utils import set_parent_app
from .routes import router


@asynccontextmanager
async def lifespan_frontend(app: FastAPI) -> AsyncIterator[None]:
    settings: ApplicationSettings = app.state.settings

    nicegui.app.include_router(router)

    nicegui.ui.run_with(
        app,
        mount_path=settings.DYNAMIC_SCHEDULER_UI_MOUNT_PATH,
        storage_secret=settings.DYNAMIC_SCHEDULER_UI_STORAGE_SECRET.get_secret_value(),
    )
    set_parent_app(app)

    yield
