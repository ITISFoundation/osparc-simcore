import logging
from typing import Final

from aiohttp import web
from celery_library import CeleryTaskManager
from celery_library.app import create_app
from celery_library.backends import RedisTaskStore
from celery_library.types import register_celery_types, register_pydantic_types
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings

from ..redis import get_redis_celery_tasks_client_sdk
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)

_APP_CELERY_TASK_MANAGER_KEY: Final = web.AppKey(CeleryTaskManager.__name__, CeleryTaskManager)


async def setup_task_manager(app: web.Application):
    with log_context(_logger, logging.INFO, "Setting up Celery task manager"):
        celery_settings: CelerySettings = get_plugin_settings(app)

        redis_client_sdk = get_redis_celery_tasks_client_sdk(app)
        celery_app = create_app(celery_settings)

        app[_APP_CELERY_TASK_MANAGER_KEY] = CeleryTaskManager(
            celery_app,
            celery_settings,
            RedisTaskStore(redis_client_sdk),
        )
        register_celery_types()

        register_pydantic_types(FoldersBody)

    yield


def get_task_manager(app: web.Application) -> TaskManager:
    return app[_APP_CELERY_TASK_MANAGER_KEY]
