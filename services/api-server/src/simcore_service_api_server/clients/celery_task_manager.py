import logging
from collections.abc import AsyncIterator

from celery_library import CeleryTaskManager
from celery_library.app import create_app
from celery_library.backends import RedisTaskStore
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from servicelib.fastapi.redis_lifespan import configure_redis_client_sdk
from servicelib.logging_utils import log_context
from servicelib.redis import RedisClientSDK
from settings_library.celery import CelerySettings
from settings_library.redis import RedisDatabase

from ..models.domain.celery_models import pydantic_types_to_register

_logger = logging.getLogger(__name__)


def configure_task_manager(app_lifespan: LifespanManager[FastAPI], settings: CelerySettings) -> None:
    configure_redis_client_sdk(
        app_lifespan,
        settings=settings.CELERY_REDIS_RESULT_BACKEND,
        database=RedisDatabase.CELERY_TASKS,
        client_name="api_server_celery_tasks",
        app_state_attr="celery_tasks_redis_client_sdk",
    )

    async def _task_manager_lifespan(app: FastAPI) -> AsyncIterator[State]:
        redis_client_sdk: RedisClientSDK = app.state.celery_tasks_redis_client_sdk
        with log_context(_logger, logging.INFO, "Setting up Celery"):
            app.state.task_manager = CeleryTaskManager(
                create_app(settings),
                settings,
                RedisTaskStore(redis_client_sdk),
            )

            register_celery_types()
            register_pydantic_types(*pydantic_types_to_register)

        yield {}

    app_lifespan.add(_task_manager_lifespan)
