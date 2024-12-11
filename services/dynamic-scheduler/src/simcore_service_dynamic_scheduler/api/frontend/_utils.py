import nicegui
from fastapi import FastAPI

from ...core.settings import ApplicationSettings


def set_parent_app(parent_app: FastAPI) -> None:
    nicegui.app.state.parent_app = parent_app


def get_parent_app(app: FastAPI) -> FastAPI:
    parent_app: FastAPI = app.state.parent_app
    return parent_app


def get_settings() -> ApplicationSettings:
    parent_app = get_parent_app(nicegui.app)
    settings: ApplicationSettings = parent_app.state.settings
    return settings
