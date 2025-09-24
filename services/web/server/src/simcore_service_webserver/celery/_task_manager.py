import logging

from aiohttp import web
from celery_library.backends.redis import RedisTaskInfoStore
from celery_library.common import create_app
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings

from ..redis import get_redis_celery_tasks_client_sdk
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)

_APP_CELERY_TASK_MANAGER = f"{__name__}.celery_task_manager"


async def setup_task_manager(app: web.Application):
    with log_context(_logger, logging.INFO, "Setting up Celery"):
        celery_settings: CelerySettings = get_plugin_settings(app)

        redis_client_sdk = get_redis_celery_tasks_client_sdk(app)
        celery_app = create_app(celery_settings)

        app[_APP_CELERY_TASK_MANAGER] = CeleryTaskManager(
            celery_app,
            celery_settings,
            RedisTaskInfoStore(redis_client_sdk),
        )
        register_celery_types()

    yield


def get_task_manager(app: web.Application) -> TaskManager:
    task_manager: CeleryTaskManager = app[_APP_CELERY_TASK_MANAGER]
    return task_manager
