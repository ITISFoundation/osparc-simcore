import logging

import tenacity
from aiohttp import web
from celery import Celery
from tenacity import before_log, stop_after_attempt, wait_fixed

from ..computation_config import ComputationSettings
from ..computation_config import get_settings as get_computation_settings
from .config import APP_CLIENT_CELERY_CLIENT_KEY

log = logging.getLogger(__name__)

retry_upon_init_policy = dict(
    stop=stop_after_attempt(4),
    wait=wait_fixed(1.5),
    before=before_log(log, logging.WARNING),
    reraise=True,
)


@tenacity.retry(**retry_upon_init_policy)
def _create_celery_app(app: web.Application) -> Celery:
    comp_settings: ComputationSettings = get_computation_settings(app)
    return Celery(
        comp_settings.task_name,
        broker=comp_settings.broker_url,
        backend=comp_settings.result_backend,
    )


def setup(app: web.Application):
    app[APP_CLIENT_CELERY_CLIENT_KEY] = celery_app = _create_celery_app(app)

    assert celery_app  # nosec


def get_celery_client(app: web.Application) -> Celery:
    return app[APP_CLIENT_CELERY_CLIENT_KEY]
