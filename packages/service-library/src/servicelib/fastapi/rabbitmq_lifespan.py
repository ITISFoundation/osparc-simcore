import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from pydantic import BaseModel, ValidationError
from settings_library.rabbit import RabbitSettings

from ..rabbitmq import wait_till_rabbitmq_responsive
from .lifespan_utils import (
    LifespanOnStartupError,
    lifespan_context,
)

_logger = logging.getLogger(__name__)


class RabbitMQConfigurationError(LifespanOnStartupError):
    msg_template = "Invalid RabbitMQ config on startup : {validation_error}"


class RabbitMQLifespanState(BaseModel):
    RABBIT_SETTINGS: RabbitSettings


async def rabbitmq_connectivity_lifespan(
    _: FastAPI, state: State
) -> AsyncIterator[State]:
    """Ensures RabbitMQ connectivity during lifespan.

    For creating clients, use additional lifespans like rabbitmq_rpc_client_context.
    """
    _lifespan_name = f"{__name__}.{rabbitmq_connectivity_lifespan.__name__}"

    with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:

        # Validate input state
        try:
            rabbit_state = RabbitMQLifespanState.model_validate(state)
            rabbit_dsn_with_secrets = rabbit_state.RABBIT_SETTINGS.dsn
        except ValidationError as exc:
            raise RabbitMQConfigurationError(validation_error=exc, state=state) from exc

        # Wait for RabbitMQ to be responsive
        await wait_till_rabbitmq_responsive(rabbit_dsn_with_secrets)

        yield {"RABBIT_CONNECTIVITY_LIFESPAN_NAME": _lifespan_name, **called_state}
