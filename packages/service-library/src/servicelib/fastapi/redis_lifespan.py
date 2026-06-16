import asyncio
import logging
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Annotated

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from pydantic import BaseModel, StringConstraints, ValidationError
from settings_library.redis import RedisDatabase, RedisSettings

from ..logging_utils import log_catch, log_context
from ..redis import RedisClientSDK, RedisClientsManager, RedisManagerDBConfig
from .lifespan_utils import (
    LifespanOnStartupError,
    PublisherLifespan,
    create_publisher_lifespan,
    lifespan_context,
)

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
            redis_dsn_with_secrets = redis_state.REDIS_SETTINGS.build_redis_dsn(redis_state.REDIS_CLIENT_DB)
        except ValidationError as exc:
            raise RedisConfigurationError(validation_error=exc, state=state) from exc

        # Setup client
        with log_context(
            _logger,
            logging.INFO,
            f"Creating redis client with name={redis_state.REDIS_CLIENT_NAME}",
        ):
            # NOTE: sdk integrates waiting until connection is ready
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


class _RedisClientsManagerLifespanState(StrEnum):
    REDIS_CLIENTS_MANAGER = "redis.clients_manager"


def _create_redis_clients_manager_lifespan(
    settings: RedisSettings,
    databases_configs: set[RedisManagerDBConfig],
    client_name: str,
) -> PublisherLifespan:
    async def _lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}._redis_clients_manager_lifespan[{client_name}]"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            manager = RedisClientsManager(
                databases_configs=databases_configs,
                settings=settings,
                client_name=client_name,
            )
            await manager.setup()

            try:
                yield {
                    _RedisClientsManagerLifespanState.REDIS_CLIENTS_MANAGER: manager,
                    **called_state,
                }
            finally:
                with log_catch(_logger, reraise=False):
                    await asyncio.wait_for(manager.shutdown(), timeout=20)

    return _lifespan


def configure_redis_clients_manager(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RedisSettings,
    databases_configs: set[RedisManagerDBConfig],
    client_name: str,
    app_state_attr: str = "redis_clients_manager",
) -> None:
    """Configure a RedisClientsManager lifespan and publish it to app.state.

    Args:
        app_lifespan: The application LifespanManager to add the Redis lifespan to.
        settings: Redis connection settings.
        databases_configs: Set of database configurations (database + decode_responses flags).
        client_name: Name used to identify this Redis client (appears in Redis CLIENT LIST).
        app_state_attr: Attribute name on app.state where the manager is stored.
            Defaults to "redis_clients_manager".
    """
    redis_lifespan_manager: LifespanManager[FastAPI] = LifespanManager()
    redis_lifespan_manager.add(_create_redis_clients_manager_lifespan(settings, databases_configs, client_name))
    redis_lifespan_manager.add(
        create_publisher_lifespan(
            state_key=_RedisClientsManagerLifespanState.REDIS_CLIENTS_MANAGER,
            app_state_attr=app_state_attr,
        )
    )
    app_lifespan.include(redis_lifespan_manager)


class _RedisClientSDKLifespanState(StrEnum):
    REDIS_CLIENT_SDK_SIMPLE = "redis.client_sdk_simple"


def _create_redis_client_sdk_lifespan(
    settings: RedisSettings,
    database: RedisDatabase,
    client_name: str,
) -> PublisherLifespan:
    async def _lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}._redis_client_sdk_lifespan[{client_name}]"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            redis_client = RedisClientSDK(
                settings.build_redis_dsn(database),
                client_name=client_name,
            )
            await redis_client.setup()

            try:
                yield {
                    _RedisClientSDKLifespanState.REDIS_CLIENT_SDK_SIMPLE: redis_client,
                    **called_state,
                }
            finally:
                with log_catch(_logger, reraise=False):
                    await asyncio.wait_for(redis_client.shutdown(), timeout=20)

    return _lifespan


def configure_redis_client_sdk(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RedisSettings,
    database: RedisDatabase,
    client_name: str,
    app_state_attr: str = "redis_client_sdk",
) -> None:
    """Configure a single RedisClientSDK lifespan and publish it to app.state.

    Args:
        app_lifespan: The application LifespanManager to add the Redis lifespan to.
        settings: Redis connection settings.
        database: The Redis database to connect to.
        client_name: Name used to identify this Redis client (appears in Redis CLIENT LIST).
        app_state_attr: Attribute name on app.state where the SDK is stored.
            Defaults to "redis_client_sdk".
    """
    redis_lifespan_manager: LifespanManager[FastAPI] = LifespanManager()
    redis_lifespan_manager.add(_create_redis_client_sdk_lifespan(settings, database, client_name))
    redis_lifespan_manager.add(
        create_publisher_lifespan(
            state_key=_RedisClientSDKLifespanState.REDIS_CLIENT_SDK_SIMPLE,
            app_state_attr=app_state_attr,
        )
    )
    app_lifespan.include(redis_lifespan_manager)
