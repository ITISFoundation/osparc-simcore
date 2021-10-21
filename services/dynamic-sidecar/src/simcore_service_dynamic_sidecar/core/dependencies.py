from fastapi import Depends, Request
from fastapi.datastructures import State

from ..models.domains.shared_store import SharedStore
from ..models.schemas.application_health import ApplicationHealth
from .settings import DynamicSidecarSettings


def get_app_state(request: Request) -> State:
    return request.app.state


def get_application_health(
    app_state: State = Depends(get_app_state),
) -> ApplicationHealth:
    return app_state.application_health  # type: ignore


def get_settings(app_state: State = Depends(get_app_state)) -> DynamicSidecarSettings:
    return app_state.settings  # type: ignore


def get_shared_store(app_state: State = Depends(get_app_state)) -> SharedStore:
    return app_state.shared_store  # type: ignore
