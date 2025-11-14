from collections.abc import Callable

from celery import Celery  # type: ignore[import-untyped]
from servicelib.celery.app_server import BaseAppServer
from settings_library.celery import CelerySettings

from ..app import create_app
from .signals import register_worker_signals


def create_worker_app(
    settings: CelerySettings,
    register_worker_tasks_cb: Callable[[Celery], None],
    app_server_factory_cb: Callable[[], BaseAppServer],
) -> Celery:
    app = create_app(settings)
    register_worker_tasks_cb(app)
    register_worker_signals(app, settings, app_server_factory_cb)

    return app
