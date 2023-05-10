import asyncio
import logging
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.long_running_tasks.client import ProgressCallback

from .....core.settings import DynamicServicesSchedulerSettings, DynamicSidecarSettings
from .....models.schemas.dynamic_services import DynamicSidecarStatus, SchedulerData
from ...api_client import DynamicSidecarClient, get_dynamic_sidecar_client
from ...docker_api import (
    get_dynamic_sidecars_to_observe,
    remove_pending_volume_removal_services,
)
from ._events_utils import service_push_outputs

logger = logging.getLogger(__name__)

# NOTE: take care in changing this message, part of it is used by
# graylog and it will break the notifications
LOG_MSG_MANUAL_INTERVENTION: Final[str] = "Service waiting for manual intervention"


async def push_service_outputs(
    app: FastAPI,
    node_uuid: NodeID,
    progress_callback: ProgressCallback | None = None,
) -> None:
    dynamic_sidecar_client: DynamicSidecarClient = get_dynamic_sidecar_client(
        app, node_uuid
    )
    await service_push_outputs(
        app=app,
        node_uuid=node_uuid,
        dynamic_sidecar_client=dynamic_sidecar_client,
        progress_callback=progress_callback,
    )


async def service_awaits_manual_interventions(scheduler_data: SchedulerData) -> bool:
    service_awaits_intervention = (
        scheduler_data.dynamic_sidecar.status.current == DynamicSidecarStatus.FAILING
        and scheduler_data.dynamic_sidecar.wait_for_manual_intervention_after_error
        is True
    )
    if (
        service_awaits_intervention
        and not scheduler_data.dynamic_sidecar.wait_for_manual_intervention_logged
    ):
        scheduler_data.dynamic_sidecar.wait_for_manual_intervention_logged = True
        logger.warning(" %s %s", LOG_MSG_MANUAL_INTERVENTION, scheduler_data.node_uuid)
    return service_awaits_intervention


async def cleanup_volume_removal_services(app: FastAPI) -> None:
    settings: DynamicServicesSchedulerSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER
    )
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )

    logger.debug(
        "dynamic-sidecars cleanup pending volume removal services every %s seconds",
        settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_PENDING_VOLUME_REMOVAL_INTERVAL_S,
    )
    while await asyncio.sleep(
        settings.DIRECTOR_V2_DYNAMIC_SCHEDULER_PENDING_VOLUME_REMOVAL_INTERVAL_S,
        True,
    ):
        logger.debug("Removing pending volume removal services...")

        try:
            await remove_pending_volume_removal_services(dynamic_sidecar_settings)
        except asyncio.CancelledError:
            logger.info("Stopped pending volume removal services task")
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error while cleaning up pending volume removal services"
            )


async def discover_running_services(schduler: "Scheduler") -> None:  # type: ignore
    """discover all services which were started before and add them to the scheduler"""
    dynamic_sidecar_settings: DynamicSidecarSettings = (
        schduler.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )
    services_to_observe: list[SchedulerData] = await get_dynamic_sidecars_to_observe(
        dynamic_sidecar_settings
    )

    logger.info("The following services need to be observed: %s", services_to_observe)

    for scheduler_data in services_to_observe:
        await schduler._add_service(scheduler_data)
