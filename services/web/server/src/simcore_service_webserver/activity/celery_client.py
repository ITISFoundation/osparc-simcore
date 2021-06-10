import logging
from typing import Optional

from aiohttp import web
from celery import Celery
from tenacity import AsyncRetrying, before_log, stop_after_attempt, wait_fixed

from ..computation_config import ComputationSettings, get_settings
from .config import CONFIG_SECTION_NAME

__APP_CLIENT_CELERY_CLIENT_KEY = ".".join(
    [__name__, CONFIG_SECTION_NAME, "celery_client"]
)

log = logging.getLogger(__name__)

retry_upon_init_policy = dict(
    stop=stop_after_attempt(4),
    wait=wait_fixed(1.5),
    before=before_log(log, logging.WARNING),
    reraise=True,
)


def _get_computation_settings(app: web.Application) -> ComputationSettings:
    return get_settings(app)


async def _celery_app(app: web.Application):
    comp_settings: ComputationSettings = _get_computation_settings(app)

    celery_app: Optional[Celery] = None
    async for attempt in AsyncRetrying(**retry_upon_init_policy):
        with attempt:
            celery_app = Celery(
                comp_settings.task_name,
                broker=comp_settings.broker_url,
                backend=comp_settings.result_backend,
            )
            if not celery_app:
                raise ValueError(
                    "Expected celery client app instance, got {celery_app}"
                )

    app[__APP_CLIENT_CELERY_CLIENT_KEY] = celery_app

    yield

    if celery_app is not app[__APP_CLIENT_CELERY_CLIENT_KEY]:
        log.critical("Invalid celery client in app")

    celery_app.close()


def setup(app: web.Application):
    app[__APP_CLIENT_CELERY_CLIENT_KEY] = None

    app.cleanup_ctx.append(_celery_app)


def get_celery_client(app: web.Application) -> Celery:
    return app[__APP_CLIENT_CELERY_CLIENT_KEY]
