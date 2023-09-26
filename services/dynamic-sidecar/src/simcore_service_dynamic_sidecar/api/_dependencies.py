""" Free functions to inject dependencies in routes handlers
"""

from asyncio import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.datastructures import State

from ..core.settings import ApplicationSettings
from ..models.schemas.application_health import ApplicationHealth
from ..models.shared_store import SharedStore
from ..modules.inputs import InputsState
from ..modules.mounted_fs import MountedVolumes
from ..modules.outputs import OutputsContext, OutputsManager
from ..modules.prometheus_metrics import UserServicesMetrics


def get_application(request: Request) -> FastAPI:
    return request.app


def get_app_state(request: Request) -> State:
    return request.app.state


def get_application_health(
    app_state: Annotated[State, Depends(get_app_state)]
) -> ApplicationHealth:
    return app_state.application_health  # type: ignore


def get_settings(
    app_state: Annotated[State, Depends(get_app_state)]
) -> ApplicationSettings:
    return app_state.settings  # type: ignore


def get_shared_store(
    app_state: Annotated[State, Depends(get_app_state)]
) -> SharedStore:
    return app_state.shared_store  # type: ignore


def get_mounted_volumes(
    app_state: Annotated[State, Depends(get_app_state)]
) -> MountedVolumes:
    return app_state.mounted_volumes  # type: ignore


def get_container_restart_lock(
    app_state: Annotated[State, Depends(get_app_state)]
) -> Lock:
    return app_state.container_restart_lock  # type: ignore


def get_outputs_manager(
    app_state: Annotated[State, Depends(get_app_state)]
) -> OutputsManager:
    return app_state.outputs_manager  # type: ignore


def get_outputs_context(
    app_state: Annotated[State, Depends(get_app_state)]
) -> OutputsContext:
    return app_state.outputs_context  # type: ignore


def get_inputs_state(
    app_state: Annotated[State, Depends(get_app_state)]
) -> InputsState:
    return app_state.inputs_state  # type: ignore


def get_user_services_metrics(
    app_state: Annotated[State, Depends(get_app_state)]
) -> UserServicesMetrics:
    return app_state.user_service_metrics  # type: ignore
