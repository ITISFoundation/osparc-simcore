import logging
from typing import Final

from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.services import ServiceType
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import NonNegativeFloat
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_context

from ...core.docker_utils import (
    get_accepted_container_count_from_names,
    get_container_statuses,
)
from ...core.rabbitmq import post_resource_tracking_message
from ...core.settings import ApplicationSettings
from ...models.shared_store import SharedStore
from ._models import ResourceTrackingState
from .settings import ResourceTrackingSettings

_STOP_WORKER_TIMEOUT_S: Final[NonNegativeFloat] = 1.0

_logger = logging.getLogger(__name__)


def _get_settings(app: FastAPI) -> ApplicationSettings:
    settings: ApplicationSettings = app.state.settings
    return settings


async def _start_heart_beat_task(app: FastAPI) -> None:
    settings: ResourceTrackingSettings = app.state.settings.RESOURCE_TRACKING
    resource_tracking: ResourceTrackingState = app.state.resource_tracking

    if resource_tracking.heart_beat_task is not None:
        msg = f"Unexpected task={resource_tracking.heart_beat_task} already running!"
        raise RuntimeError(msg)

    with log_context(_logger, logging.DEBUG, "starting heart beat task"):
        resource_tracking.heart_beat_task = start_periodic_task(
            _heart_beat_task,
            app=app,
            interval=settings.RESOURCE_TRACKING_HEARTBEAT_INTERVAL,
            task_name="resource_tracking_heart_beat",
        )


async def stop_heart_beat_task(app: FastAPI) -> None:
    # NOTE: this is only used by the teardown
    await __stop_heart_beat_task(app)


async def __stop_heart_beat_task(app: FastAPI) -> None:
    resource_tracking: ResourceTrackingState = app.state.resource_tracking
    if resource_tracking.heart_beat_task:
        await stop_periodic_task(
            resource_tracking.heart_beat_task, timeout=_STOP_WORKER_TIMEOUT_S
        )


async def _heart_beat_task(app: FastAPI):
    settings: ApplicationSettings = _get_settings(app)
    shared_store: SharedStore = app.state.shared_store

    accepted_container_count = await get_accepted_container_count_from_names(
        shared_store.container_names
    )
    if accepted_container_count == len(shared_store.container_names):
        message = RabbitResourceTrackingHeartbeatMessage(
            service_run_id=settings.DY_SIDECAR_RUN_ID
        )
        await post_resource_tracking_message(app, message)
    else:
        container_statuses = await get_container_statuses(shared_store.container_names)
        _logger.info(
            "heart beat skipped containers=%s container_statuses=%s",
            shared_store.container_names,
            container_statuses,
        )


async def send_service_stopped(
    app: FastAPI, simcore_platform_status: SimcorePlatformStatus
) -> None:
    # NOTE: calling `stop_heart_beat_task` in place of `__stop_heart_beat_task` does not work.
    # Somehow the function does not get called.
    # After spending a lot of time on figuring this out, the current is the best I can offer.
    # If you want to refactor this talk with ANE first before sinking more time in it.
    await __stop_heart_beat_task(app)

    settings: ApplicationSettings = _get_settings(app)
    message = RabbitResourceTrackingStoppedMessage(
        service_run_id=settings.DY_SIDECAR_RUN_ID,
        simcore_platform_status=simcore_platform_status,
    )
    await post_resource_tracking_message(app, message)


async def send_service_started(
    app: FastAPI, *, metrics_params: CreateServiceMetricsAdditionalParams
) -> None:
    settings: ApplicationSettings = _get_settings(app)

    message = RabbitResourceTrackingStartedMessage(
        service_run_id=settings.DY_SIDECAR_RUN_ID,
        wallet_id=metrics_params.wallet_id,
        wallet_name=metrics_params.wallet_name,
        product_name=metrics_params.product_name,
        simcore_user_agent=metrics_params.simcore_user_agent,
        user_id=settings.DY_SIDECAR_USER_ID,
        user_email=metrics_params.user_email,
        project_id=settings.DY_SIDECAR_PROJECT_ID,
        project_name=metrics_params.project_name,
        node_id=settings.DY_SIDECAR_NODE_ID,
        node_name=metrics_params.node_name,
        service_key=metrics_params.service_key,
        service_version=metrics_params.service_version,
        service_type=ServiceType.DYNAMIC,
        service_resources=metrics_params.service_resources,
        service_additional_metadata=metrics_params.service_additional_metadata,
    )
    await post_resource_tracking_message(app, message)

    await _start_heart_beat_task(app)
