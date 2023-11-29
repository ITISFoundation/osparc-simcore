from typing import Annotated, cast

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app
from servicelib.rabbitmq import RabbitMQClient

from ...services.log_streaming import LogDistributor


def get_rabbitmq_client(app: Annotated[FastAPI, Depends(get_app)]) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_log_distributor(app: Annotated[FastAPI, Depends(get_app)]) -> LogDistributor:
    assert app.state.log_distributor  # nosec
    return cast(LogDistributor, app.state.log_distributor)
