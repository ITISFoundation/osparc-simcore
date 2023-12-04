from typing import Annotated, cast

from fastapi import Depends, FastAPI
from pydantic import NonNegativeInt
from servicelib.fastapi.dependencies import get_app
from servicelib.rabbitmq import RabbitMQClient

from ...services.log_streaming import LogDistributor


def get_rabbitmq_client(app: Annotated[FastAPI, Depends(get_app)]) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_log_distributor(app: Annotated[FastAPI, Depends(get_app)]) -> LogDistributor:
    assert app.state.log_distributor  # nosec
    return cast(LogDistributor, app.state.log_distributor)


def get_max_log_check_seconds(
    app: Annotated[FastAPI, Depends(get_app)]
) -> NonNegativeInt:
    assert app.state.settings  # nosec
    return cast(NonNegativeInt, app.state.settings.API_SERVER_MAX_LOG_CHECK_SECONDS)
