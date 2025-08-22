import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from pydantic import BaseModel, StringConstraints, ValidationError
from settings_library.redis import RedisDatabase, RedisSettings

from ..logging_utils import log_catch, log_context
from ..redis import RedisClientSDK
from .lifespan_utils import LifespanOnStartupError, lifespan_context

_logger = logging.getLogger(__name__)


class RedisConfigurationError(LifespanOnStartupError):
    msg_template = "Invalid redis config on startup : {validation_error}"


class RedisLifespanState(BaseModel):
    REDIS_SETTINGS: RedisSettings
    REDIS_CLIENT_NAME: Annotated[str, StringConstraints(min_length=3, max_length=32)]
    REDIS_CLIENT_DB: RedisDatabase


async def redis_client_sdk_lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:
    _lifespan_name = f"{__name__}.{redis_client_sdk_lifespan.__name__}"

    with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:

        # Validate input state
        try:
            redis_state = RedisLifespanState.model_validate(state)
            redis_dsn_with_secrets = redis_state.REDIS_SETTINGS.build_redis_dsn(
                redis_state.REDIS_CLIENT_DB
            )
        except ValidationError as exc:
            raise RedisConfigurationError(validation_error=exc, state=state) from exc

        # Setup client
        with log_context(
            _logger,
            logging.INFO,
            f"Creating redis client with name={redis_state.REDIS_CLIENT_NAME}",
        ):
            # NOTE: sdk integrats waiting until connection is ready
            # and will raise an exception if it cannot connect
            redis_client = RedisClientSDK(
                redis_dsn_with_secrets,
                client_name=redis_state.REDIS_CLIENT_NAME,
            )
            await redis_client.setup()

        try:
            yield {"REDIS_CLIENT_SDK": redis_client, **called_state}
        finally:
            # Teardown client
            with log_catch(_logger, reraise=False):
                await asyncio.wait_for(
                    redis_client.shutdown(),
                    # NOTE: shutdown already has a _HEALTHCHECK_TASK_TIMEOUT_S of 10s
                    timeout=20,
                )
