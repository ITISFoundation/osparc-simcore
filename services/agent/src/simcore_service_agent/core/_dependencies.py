""" Free functions to inject dependencies in routes handlers
"""

from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from servicelib.rabbitmq._client import RabbitMQClient

from .settings import ApplicationSettings


def get_application(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)


def get_settings(
    app: Annotated[FastAPI, Depends(get_application)]
) -> ApplicationSettings:
    assert isinstance(app.state.settings, ApplicationSettings)  # nosec
    return app.state.settings


def get_rabbitmq_client(
    app: Annotated[FastAPI, Depends(get_application)]
) -> RabbitMQClient:
    assert isinstance(app.state.rabbitmq, RabbitMQClient)  # nosec
    return app.state.rabbitmq
