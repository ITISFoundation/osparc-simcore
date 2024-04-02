import asyncio
from time import time
from typing import Annotated, Final, cast

from fastapi import Depends, FastAPI
from pydantic import NonNegativeInt
from servicelib.aiohttp.application_setup import ApplicationSetupError
from servicelib.fastapi.dependencies import get_app
from servicelib.rabbitmq import RabbitMQClient

from ...services.log_streaming import LogDistributor

_MAX_WAIT_FOR_LOG_DISTRIBUTOR_SECONDS: Final[int] = 10


def get_rabbitmq_client(app: Annotated[FastAPI, Depends(get_app)]) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_log_distributor(app: Annotated[FastAPI, Depends(get_app)]) -> LogDistributor:
    assert app.state.log_distributor  # nosec
    return cast(LogDistributor, app.state.log_distributor)


async def wait_till_log_distributor_ready(app) -> None:
    start = time()
    while not hasattr(app.state, "log_distributor"):
        if time() - start > _MAX_WAIT_FOR_LOG_DISTRIBUTOR_SECONDS:
            raise ApplicationSetupError(
                f"Api server's log_distributor was not ready within {_MAX_WAIT_FOR_LOG_DISTRIBUTOR_SECONDS=} seconds"
            )
        await asyncio.sleep(1)
    return


def get_log_check_timeout(app: Annotated[FastAPI, Depends(get_app)]) -> NonNegativeInt:
    assert app.state.settings  # nosec
    return cast(NonNegativeInt, app.state.settings.API_SERVER_LOG_CHECK_TIMEOUT_SECONDS)
