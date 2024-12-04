import nicegui
from fastapi import FastAPI


def set_parent_app(parent_app: FastAPI) -> None:
    nicegui.app.state.parent_app = parent_app


def get_parent_app(app: FastAPI) -> FastAPI:
    parent_app: FastAPI = app.state.parent_app
    return parent_app
