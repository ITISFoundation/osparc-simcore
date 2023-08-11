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
from servicelib.background_task import stop_periodic_task
from servicelib.logging_utils import log_context

from ...core.rabbitmq import post_resource_tracking_message
from ...core.settings import ApplicationSettings
from ._models import ResourceTrackingState

_STOP_WORKER_TIMEOUT_S: Final[NonNegativeFloat] = 1.0

_logger = logging.getLogger(__name__)


def _get_settings(app: FastAPI) -> ApplicationSettings:
    settings: ApplicationSettings = app.state.settings
    return settings


async def stop_heart_beat_task(app: FastAPI) -> None:
    resource_tracking: ResourceTrackingState = app.state.resource_tracking
    with log_context(_logger, logging.DEBUG, "resource tracking shutdown"):
        if resource_tracking.heart_beat_task:
            await stop_periodic_task(
                resource_tracking.heart_beat_task,
                timeout=_STOP_WORKER_TIMEOUT_S,
            )


async def send_service_stopped(
    app: FastAPI, simcore_platform_status: SimcorePlatformStatus
) -> None:
    settings: ApplicationSettings = _get_settings(app)

    message = RabbitResourceTrackingStoppedMessage(
        service_run_id=settings.DY_SIDECAR_RUN_ID,
        simcore_platform_status=simcore_platform_status,
    )
    await post_resource_tracking_message(app, message)

    await stop_heart_beat_task(app)


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


async def heart_beat_task(app: FastAPI):
    # NOTE: heartbeat is sent regardless of the status of the containers
    # while this sidecar is active it will be sent
    # Should this be different?

    settings: ApplicationSettings = _get_settings(app)

    message = RabbitResourceTrackingHeartbeatMessage(
        service_run_id=settings.DY_SIDECAR_RUN_ID
    )
    await post_resource_tracking_message(app, message)
