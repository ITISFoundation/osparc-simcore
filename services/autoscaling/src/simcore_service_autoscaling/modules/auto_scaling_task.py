import json
import logging
from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import FastAPI
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.redis_utils import exclusive

from ..core.settings import ApplicationSettings
from .auto_scaling_core import auto_scale_cluster
from .auto_scaling_mode_computational import ComputationalAutoscaling
from .auto_scaling_mode_dynamic import DynamicAutoscaling
from .buffer_machine_core import monitor_buffer_machines
from .redis import get_redis_client

_TASK_NAME: Final[str] = "Autoscaling EC2 instances"
_TASK_NAME_BUFFER: Final[str] = f"{_TASK_NAME} Buffers"

logger = logging.getLogger(__name__)


def _create_lock_key_and_value(app: FastAPI) -> tuple[str, str]:
    app_settings: ApplicationSettings = app.state.settings
    lock_key_parts = [app.title, app.version]
    lock_value = ""
    if app_settings.AUTOSCALING_NODES_MONITORING:
        lock_key_parts += [
            "dynamic",
            app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
        ]
        lock_value = json.dumps(
            {
                "node_labels": app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
            }
        )
    elif app_settings.AUTOSCALING_DASK:
        lock_key_parts += [
            "computational",
            app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL,
        ]
        lock_value = json.dumps(
            {"scheduler_url": app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL}
        )
    lock_key = ":".join(f"{k}" for k in lock_key_parts)
    return lock_key, lock_value


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        lock_key, lock_value = _create_lock_key_and_value(app)
        assert lock_key  # nosec
        assert lock_value  # nosec
        app.state.autoscaler_task = start_periodic_task(
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
        if app_settings.AUTOSCALING_NODES_MONITORING:
            app.state.autoscaler_task_buffers = start_periodic_task(
                exclusive(
                    get_redis_client(app),
                    lock_key=f"{lock_key}_buffers",
                    lock_value=lock_value,
                )(monitor_buffer_machines),
                interval=app_settings.AUTOSCALING_POLL_INTERVAL,
                task_name=_TASK_NAME_BUFFER,
                app=app,
                auto_scaling_mode=(DynamicAutoscaling()),
            )

    return _startup


def on_app_shutdown(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        await stop_periodic_task(app.state.autoscaler_task)
        if app.state.autoscaler_task_buffers:
            await stop_periodic_task(app.state.autoscaler_task_buffers)

    return _stop


def setup(app: FastAPI):
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
        logger.warning(
            "the autoscaling background task is disabled by settings, nothing will happen!"
        )
        return
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
