import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError
from servicelib.logging_utils import log_catch, log_context
from settings_library.redis import RedisDatabase, RedisSettings

from ..redis import RedisClientSDK
from .lifespan_utils import LifespanOnStartupError

_logger = logging.getLogger(__name__)


class RedisConfigurationError(LifespanOnStartupError):
    msg_template = "Invalid redis config on startup : {validation_error}"


class RedisLifespanState(BaseModel):
    REDIS_SETTINGS: RedisSettings
    REDIS_CLIENT_NAME: Annotated[str, StringConstraints(min_length=3, max_length=32)]
    REDIS_CLIENT_DB: RedisDatabase

    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,  # RedisClientSDK has some arbitrary types and this class will never be serialized
    )


async def redis_database_lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:

    with log_context(_logger, logging.INFO, f"{__name__}"):

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

            redis_client = RedisClientSDK(
                redis_dsn_with_secrets,
                client_name=redis_state.REDIS_CLIENT_NAME,
            )

        try:

            yield {"REDIS_CLIENT_SDK": redis_client}

        finally:
            # Teardown client
            if redis_client:
                with log_catch(_logger, reraise=False):
                    await asyncio.wait_for(
                        redis_client.shutdown(),
                        # NOTE: shutdown already has a _HEALTHCHECK_TASK_TIMEOUT_S of 10s
                        timeout=20,
                    )
