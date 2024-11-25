import nicegui
from fastapi import FastAPI

from ...core.settings import ApplicationSettings
from ._router import router
from ._utils import set_parent_app


def setup_frontend(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    nicegui.app.include_router(router)

    nicegui.ui.run_with(
        app, mount_path="/", storage_secret=settings.DYNAMIC_SCHEDULER_UI_STORAGE_SECRET
    )
    set_parent_app(app)
