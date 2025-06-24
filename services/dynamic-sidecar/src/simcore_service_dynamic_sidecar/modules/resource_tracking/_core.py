import asyncio
import logging
from typing import Final

from common_library.async_tools import cancel_and_shielded_wait
from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import ContainerState
from models_library.rabbitmq_messages import (
    DynamicServiceRunningMessage,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.services import ServiceType
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import NonNegativeFloat
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_context

from ...core.docker_utils import (
    are_all_containers_in_expected_states,
    get_container_states,
)
from ...core.rabbitmq import (
    post_dynamic_service_running_message,
    post_resource_tracking_message,
)
from ...core.settings import ApplicationSettings, ResourceTrackingSettings
from ...models.shared_store import SharedStore
from ._models import ResourceTrackingState

_STOP_WORKER_TIMEOUT_S: Final[NonNegativeFloat] = 1.0

_logger = logging.getLogger(__name__)


def _get_settings(app: FastAPI) -> ApplicationSettings:
    settings: ApplicationSettings = app.state.settings
    return settings


async def _start_heart_beat_task(app: FastAPI) -> None:
    settings: ApplicationSettings = _get_settings(app)
    resource_tracking_settings: ResourceTrackingSettings = settings.RESOURCE_TRACKING
    resource_tracking: ResourceTrackingState = app.state.resource_tracking

    if resource_tracking.heart_beat_task is not None:
        msg = f"Unexpected task={resource_tracking.heart_beat_task} already running!"
        raise RuntimeError(msg)

    with log_context(_logger, logging.DEBUG, "starting heart beat task"):
        resource_tracking.heart_beat_task = create_periodic_task(
            _heart_beat_task,
            app=app,
            interval=resource_tracking_settings.RESOURCE_TRACKING_HEARTBEAT_INTERVAL,
            task_name="resource_tracking_heart_beat",
            wait_before_running=resource_tracking_settings.RESOURCE_TRACKING_HEARTBEAT_INTERVAL,
        )


async def stop_heart_beat_task(app: FastAPI) -> None:
    resource_tracking: ResourceTrackingState = app.state.resource_tracking
    if resource_tracking.heart_beat_task:
        await cancel_and_shielded_wait(
            resource_tracking.heart_beat_task, max_delay=_STOP_WORKER_TIMEOUT_S
        )


async def _heart_beat_task(app: FastAPI):
    settings: ApplicationSettings = _get_settings(app)
    shared_store: SharedStore = app.state.shared_store

    container_states: dict[str, ContainerState | None] = await get_container_states(
        shared_store.container_names
    )

    if are_all_containers_in_expected_states(container_states.values()):
        rut_message = RabbitResourceTrackingHeartbeatMessage(
            service_run_id=settings.DY_SIDECAR_RUN_ID
        )
        dyn_message = DynamicServiceRunningMessage(
            project_id=settings.DY_SIDECAR_PROJECT_ID,
            node_id=settings.DY_SIDECAR_NODE_ID,
            user_id=settings.DY_SIDECAR_USER_ID,
            product_name=settings.DY_SIDECAR_PRODUCT_NAME,
        )
        await asyncio.gather(
            *[
                post_resource_tracking_message(app, rut_message),
                post_dynamic_service_running_message(app, dyn_message),
            ]
        )
    else:
        _logger.info(
            "heart beat message skipped: container_states=%s", container_states
        )


async def send_service_stopped(
    app: FastAPI, simcore_platform_status: SimcorePlatformStatus
) -> None:
    await stop_heart_beat_task(app)

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
        parent_project_id=settings.DY_SIDECAR_PROJECT_ID,
        root_parent_project_id=settings.DY_SIDECAR_PROJECT_ID,
        root_parent_project_name=metrics_params.project_name,
        parent_node_id=settings.DY_SIDECAR_NODE_ID,
        root_parent_node_id=settings.DY_SIDECAR_NODE_ID,
        service_key=metrics_params.service_key,
        service_version=metrics_params.service_version,
        service_type=ServiceType.DYNAMIC,
        service_resources=metrics_params.service_resources,
        service_additional_metadata=metrics_params.service_additional_metadata,
        pricing_plan_id=metrics_params.pricing_plan_id,
        pricing_unit_id=metrics_params.pricing_unit_id,
        pricing_unit_cost_id=metrics_params.pricing_unit_cost_id,
    )
    await post_resource_tracking_message(app, message)

    await _start_heart_beat_task(app)
