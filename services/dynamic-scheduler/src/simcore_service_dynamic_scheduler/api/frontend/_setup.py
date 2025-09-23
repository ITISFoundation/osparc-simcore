import nicegui
from fastapi import FastAPI

from ...core.settings import ApplicationSettings
from . import routes_external_scheduler, routes_internal_scheduler
from ._utils import set_parent_app


def initialize_frontend(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    if settings.DYNAMIC_SCHEDULER_USE_INTERNAL_SCHEDULER:
        nicegui.app.include_router(routes_internal_scheduler.router)
    else:
        nicegui.app.include_router(routes_external_scheduler.router)

    nicegui.ui.run_with(
        app,
        mount_path=settings.DYNAMIC_SCHEDULER_UI_MOUNT_PATH,
        storage_secret=settings.DYNAMIC_SCHEDULER_UI_STORAGE_SECRET.get_secret_value(),
    )
    set_parent_app(app)
