import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitResourceTrackingBaseMessage
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.redis import CouldNotAcquireLockError
from servicelib.redis_utils import exclusive
from settings_library.rabbit import RabbitSettings

from .core.settings import ApplicationSettings
from .modules.rabbitmq import get_rabbitmq_client
from .modules.redis import get_redis_client
from .resource_tracker_background_task import periodic_check_of_running_services_task
from .resource_tracker_process_messages import process_message

_logger = logging.getLogger(__name__)

_TASK_NAME_START_PERIODIC_TASK = "start_background_task"
_TASK_NAME_PERIODICALY_CHECK_RUNNING_SERVICES = "periodic_check_of_running_services"

_RUT_MESSAGE_TTL_IN_MS = 2 * 60 * 60 * 1000  # 2 hours


async def _subscribe_to_rabbitmq(app) -> str:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channel"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queue: str = await rabbit_client.subscribe(
            RabbitResourceTrackingBaseMessage.get_channel_name(),
            message_handler=functools.partial(process_message, app),
            exclusive_queue=False,
            message_ttl=_RUT_MESSAGE_TTL_IN_MS,
        )
        return subscribed_queue


async def _start_background_task(_app: FastAPI, _interval: timedelta) -> None:
    """With this mechanism each replica of RUT is periodically trying to start
    'periodic_check_of_running_services_task'. When it is sucesfully started the task runs
    exclusively what is secured with Redis Lock Mechanism. When this lock is release
    for example when the replica dies then other replicate takes over the task."""

    lock_key = f"{_app.title}:periodic_check_of_running_services_task_lock"
    lock_value = f"locked from {datetime.now(tz=timezone.utc)}"

    try:
        await exclusive(
            get_redis_client(_app), lock_key=lock_key, lock_value=lock_value
        )(start_periodic_task)(
            periodic_check_of_running_services_task,
            interval=_interval,
            task_name=_TASK_NAME_PERIODICALY_CHECK_RUNNING_SERVICES,
            app=_app,
        )
    except CouldNotAcquireLockError:
        _logger.debug(
            "CouldNotAcquireLockError for lock_key: %s and lock_value: %s",
            lock_key,
            lock_value,
        )
    except Exception as e:
        _logger.exception(e)
        raise


def on_app_startup(app: FastAPI) -> Callable[[], Awaitable[None]]:
    async def _startup() -> None:
        with log_context(
            _logger, logging.INFO, msg="setup resource tracker"
        ), log_catch(_logger, reraise=False):
            app_settings: ApplicationSettings = app.state.settings
            app.state.resource_tracker_rabbitmq_consumer = None
            app.state.resource_tracker_background_task = None
            settings: RabbitSettings | None = (
                app_settings.RESOURCE_USAGE_TRACKER_RABBITMQ
            )
            if not settings:
                _logger.warning("RabbitMQ client is de-activated in the settings")
                return
            app.state.resource_tracker_rabbitmq_consumer = await _subscribe_to_rabbitmq(
                app
            )
            # Setup periodic task that will try to run "periodic_check_of_running_services_task"
            if app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_CHECK_ENABLED:
                app.state.resource_tracker_background_task = start_periodic_task(
                    _start_background_task,
                    interval=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC,
                    task_name=_TASK_NAME_START_PERIODIC_TASK,
                    _app=app,
                    _interval=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC,
                )

    return _startup


def on_app_shutdown(
    _app: FastAPI,
) -> Callable[[], Awaitable[None]]:
    async def _stop() -> None:
        # NOTE: We want to have persistent queue, therefore we will not unsubscribe
        assert _app  # nosec
        if _app.state.resource_tracker_background_task:
            await stop_periodic_task(_app.state.resource_tracker_background_task)

    return _stop


def setup(app: FastAPI) -> None:
    app.add_event_handler("startup", on_app_startup(app))
    app.add_event_handler("shutdown", on_app_shutdown(app))
