"""Free functions to inject dependencies in routes handlers"""

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from fastapi.datastructures import State
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ...core import rabbitmq
from ...models.schemas.application_health import ApplicationHealth
from ...modules.prometheus_metrics import UserServicesMetrics


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def _get_app_state(request: Request) -> State:
    return cast(State, request.app.state)


def get_application_health(
    app_state: Annotated[State, Depends(_get_app_state)],
) -> ApplicationHealth:
    return cast(ApplicationHealth, app_state.application_health)


def get_user_services_metrics(
    app_state: Annotated[State, Depends(_get_app_state)],
) -> UserServicesMetrics:
    return cast(UserServicesMetrics, app_state.user_service_metrics)


def get_rabbitmq_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQClient:
    return rabbitmq.get_rabbitmq_client(app)


def get_rabbitmq_rpc_client(
    app: Annotated[FastAPI, Depends(get_application)],
) -> RabbitMQRPCClient:
    return rabbitmq.get_rabbitmq_rpc_client(app)
