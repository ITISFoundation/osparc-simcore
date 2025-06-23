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
from ._buffer_machines_pool_core import monitor_buffer_machines
from ._provider_dynamic import DynamicAutoscaling

_TASK_NAME_BUFFER: Final[str] = "Autoscaling Buffer Machines Pool"

_logger = logging.getLogger(__name__)


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        app_settings: ApplicationSettings = app.state.settings
        lock_key, lock_value = create_lock_key_and_value(app)
        assert lock_key  # nosec
        assert lock_value  # nosec

        assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
        app.state.buffers_pool_task = create_periodic_task(
            exclusive(
                get_redis_client(app),
                lock_key=f"{lock_key}_buffers_pool",
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
        if hasattr(app.state, "buffers_pool_task"):
            await cancel_wait_task(app.state.buffers_pool_task)

    return _stop


def setup(app: FastAPI):
    app_settings: ApplicationSettings = app.state.settings
    if (
        any(
            s is None
            for s in [
                app_settings.AUTOSCALING_EC2_ACCESS,
                app_settings.AUTOSCALING_EC2_INSTANCES,
                app_settings.AUTOSCALING_SSM_ACCESS,
            ]
        )
        or all(
            s is None
            for s in [
                app_settings.AUTOSCALING_NODES_MONITORING,
                app_settings.AUTOSCALING_DASK,
            ]
        )
        or not app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ATTACHED_IAM_PROFILE  # type: ignore[union-attr] # checked above
    ):
        _logger.warning(
            "%s task is disabled by settings, there will be no buffer v2!",
            _TASK_NAME_BUFFER,
        )
        return
    if app_settings.AUTOSCALING_NODES_MONITORING:
        # NOTE: currently only available for dynamic autoscaling
        app.add_event_handler("startup", on_app_startup(app))
        app.add_event_handler("shutdown", on_app_shutdown(app))
