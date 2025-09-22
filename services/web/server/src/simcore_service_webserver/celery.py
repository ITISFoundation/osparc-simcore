import logging

from aiohttp import web
from celery_library.backends.redis import RedisTaskInfoStore
from celery_library.common import create_app
from celery_library.task_manager import CeleryTaskManager
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from settings_library.celery import CelerySettings
from simcore_service_webserver.constants import APP_SETTINGS_KEY
from simcore_service_webserver.redis import get_redis_celery_tasks_client_sdk

_logger = logging.getLogger(__name__)

_APP_CELERY_TASK_MANAGER = f"{__name__}.celery_task_manager"


# SETTINGS --------------------------------------------------------------------------


def get_plugin_settings(app: web.Application) -> CelerySettings:
    settings: CelerySettings | None = app[APP_SETTINGS_KEY].WEBSERVER_CELERY
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, CelerySettings)  # nosec
    return settings


# EVENTS --------------------------------------------------------------------------


async def setup_celery_task_manager(app: web.Application):
    with log_context(_logger, logging.INFO, "Setting up Celery"):
        celery_settings: CelerySettings = get_plugin_settings(app)

        redis_client_sdk = get_redis_celery_tasks_client_sdk(app)

        app[_APP_CELERY_TASK_MANAGER] = CeleryTaskManager(
            create_app(celery_settings),
            celery_settings,
            RedisTaskInfoStore(redis_client_sdk),
        )

    yield


def get_task_manager(app: web.Application) -> TaskManager:
    return app[_APP_CELERY_TASK_MANAGER]


# PLUGIN SETUP --------------------------------------------------------------------------


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_CELERY", logger=_logger
)
def setup_celery(app: web.Application):
    app.cleanup_ctx.append(setup_celery_task_manager)
