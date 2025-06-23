import logging
from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import FastAPI
from servicelib.async_utils import cancel_wait_task
from servicelib.background_task import create_periodic_task
from servicelib.redis import exclusive

from ...core.settings import ApplicationSettings
from ...utils.redis import create_lock_key_and_value
from ..redis import get_redis_client
from ._auto_scaling_core import auto_scale_cluster
from .auto_scaling_mode_computational import ComputationalAutoscaling
from .auto_scaling_mode_dynamic import DynamicAutoscaling

_TASK_NAME: Final[str] = "Autoscaling EC2 instances"

_logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        lock_key, lock_value = create_lock_key_and_value(app)
        assert lock_key  # nosec
        assert lock_value  # nosec
        app.state.autoscaler_task = create_periodic_task(
            exclusive(get_redis_client(app), lock_key=lock_key, lock_value=lock_value)(
                auto_scale_cluster
            ),
            interval=app_settings.AUTOSCALING_POLL_INTERVAL,
            task_name=_TASK_NAME,
            app=app,
            auto_scaling_mode=(
                DynamicAutoscaling()
                if app_settings.AUTOSCALING_NODES_MONITORING is not None
                else ComputationalAutoscaling()
            ),
        )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        await cancel_wait_task(app.state.autoscaler_task)

    return _stop


def setup(app: FastAPI) -> None:
    app_settings: ApplicationSettings = app.state.settings
    if any(
        s is None
        for s in [
            app_settings.AUTOSCALING_EC2_ACCESS,
            app_settings.AUTOSCALING_EC2_INSTANCES,
        ]
    ) or all(
        s is None
        for s in [
            app_settings.AUTOSCALING_NODES_MONITORING,
            app_settings.AUTOSCALING_DASK,
        ]
    ):
        _logger.warning(
            "the autoscaling background task is disabled by settings, nothing will happen!"
        )
        return
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
