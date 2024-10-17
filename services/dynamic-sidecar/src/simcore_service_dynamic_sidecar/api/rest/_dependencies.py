""" Free functions to inject dependencies in routes handlers
"""

from asyncio import Lock
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from fastapi.datastructures import State
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ...core import rabbitmq
from ...core.settings import ApplicationSettings
from ...models.schemas.application_health import ApplicationHealth
from ...models.shared_store import SharedStore
from ...modules.inputs import InputsState
from ...modules.mounted_fs import MountedVolumes
from ...modules.outputs import OutputsContext, OutputsManager
from ...modules.prometheus_metrics import UserServicesMetrics


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_app_state(request: Request) -> State:
    return cast(State, request.app.state)


def get_application_health(
    app_state: Annotated[State, Depends(get_app_state)]
) -> ApplicationHealth:
    return cast(ApplicationHealth, app_state.application_health)


def get_settings(
    app_state: Annotated[State, Depends(get_app_state)]
) -> ApplicationSettings:
    return cast(ApplicationSettings, app_state.settings)


def get_shared_store(
    app_state: Annotated[State, Depends(get_app_state)]
) -> SharedStore:
    return cast(SharedStore, app_state.shared_store)


def get_mounted_volumes(
    app_state: Annotated[State, Depends(get_app_state)]
) -> MountedVolumes:
    return cast(MountedVolumes, app_state.mounted_volumes)


def get_container_restart_lock(
    app_state: Annotated[State, Depends(get_app_state)]
) -> Lock:
    return cast(Lock, app_state.container_restart_lock)


def get_outputs_manager(
    app_state: Annotated[State, Depends(get_app_state)]
) -> OutputsManager:
    return cast(OutputsManager, app_state.outputs_manager)


def get_outputs_context(
    app_state: Annotated[State, Depends(get_app_state)]
) -> OutputsContext:
    return cast(OutputsContext, app_state.outputs_context)


def get_inputs_state(
    app_state: Annotated[State, Depends(get_app_state)]
) -> InputsState:
    return cast(InputsState, app_state.inputs_state)


def get_user_services_metrics(
    app_state: Annotated[State, Depends(get_app_state)]
) -> UserServicesMetrics:
    return cast(UserServicesMetrics, app_state.user_service_metrics)


def get_rabbitmq_client(
    app: Annotated[FastAPI, Depends(get_application)]
) -> RabbitMQClient:
    return rabbitmq.get_rabbitmq_client(app)


def get_rabbitmq_rpc_server(
    app: Annotated[FastAPI, Depends(get_application)]
) -> RabbitMQRPCClient:
    return rabbitmq.get_rabbitmq_rpc_server(app)
