from fastapi import Depends, Request
from fastapi.datastructures import State

from .settings import DynamicSidecarSettings
from .shared_store import SharedStore


def get_app_state(request: Request) -> State:
    return request.app.state  # type: ignore


def get_settings(app_state: State = Depends(get_app_state)) -> DynamicSidecarSettings:
    return app_state.settings  # type: ignore


def get_shared_store(app_state: State = Depends(get_app_state)) -> SharedStore:
    return app_state.shared_store  # type: ignore
