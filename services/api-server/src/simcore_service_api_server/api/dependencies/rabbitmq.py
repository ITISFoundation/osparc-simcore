import logging
from typing import Annotated, Final, cast

from fastapi import Depends, FastAPI
from pydantic import NonNegativeInt
from servicelib.aiohttp.application_setup import ApplicationSetupError
from servicelib.fastapi.dependencies import get_app
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from tenacity import before_sleep_log, retry, stop_after_delay, wait_fixed

from ...services.log_streaming import LogDistributor

_MAX_WAIT_FOR_LOG_DISTRIBUTOR_SECONDS: Final[int] = 10

_logger = logging.getLogger(__name__)


def get_rabbitmq_rpc_client(
    app: Annotated[FastAPI, Depends(get_app)]
) -> RabbitMQRPCClient:
    assert app.state.rabbitmq_rpc_client  # nosec
    return cast(RabbitMQRPCClient, app.state.rabbitmq_rpc_client)


def get_rabbitmq_client(app: Annotated[FastAPI, Depends(get_app)]) -> RabbitMQClient:
    assert app.state.rabbitmq_client  # nosec
    return cast(RabbitMQClient, app.state.rabbitmq_client)


def get_log_distributor(app: Annotated[FastAPI, Depends(get_app)]) -> LogDistributor:
    assert app.state.log_distributor  # nosec
    return cast(LogDistributor, app.state.log_distributor)


@retry(
    wait=wait_fixed(2),
    stop=stop_after_delay(_MAX_WAIT_FOR_LOG_DISTRIBUTOR_SECONDS),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
    reraise=True,
)
async def wait_till_log_distributor_ready(app) -> None:
    if not hasattr(app.state, "log_distributor"):
        msg = f"Api server's log_distributor was not ready within {_MAX_WAIT_FOR_LOG_DISTRIBUTOR_SECONDS=} seconds"
        raise ApplicationSetupError(msg)


def get_log_check_timeout(app: Annotated[FastAPI, Depends(get_app)]) -> NonNegativeInt:
    assert app.state.settings  # nosec
    return cast(NonNegativeInt, app.state.settings.API_SERVER_LOG_CHECK_TIMEOUT_SECONDS)
