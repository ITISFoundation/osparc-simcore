import asyncio
import logging
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.long_running_tasks.client import ProgressCallback

from .....core.settings import DynamicServicesSchedulerSettings, DynamicSidecarSettings
from .....models.schemas.dynamic_services import (
    DynamicSidecarStatus,
    RunningDynamicServiceDetails,
    SchedulerData,
    ServiceState,
)
from ...api_client import SidecarsClient, get_sidecars_client
from ...docker_api import (
    get_dynamic_sidecar_state,
    get_dynamic_sidecars_to_observe,
    remove_pending_volume_removal_services,
)
from ...docker_states import extract_containers_minimum_statuses
from ...errors import DockerServiceNotFoundError
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
    sidecars_client: SidecarsClient = get_sidecars_client(app, node_uuid)
    await service_push_outputs(
        app=app,
        node_uuid=node_uuid,
        sidecars_client=sidecars_client,
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
        await schduler._add_service(scheduler_data)  # pylint: disable=protected-access


async def get_stack_status_from_scheduler_data(
    scheduler_data: SchedulerData,
) -> RunningDynamicServiceDetails:
    # pylint: disable=too-many-return-statements

    # check if there was an error picked up by the scheduler
    # and marked this service as failed
    if scheduler_data.dynamic_sidecar.status.current != DynamicSidecarStatus.OK:
        return RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.FAILED,
            service_message=scheduler_data.dynamic_sidecar.status.info,
        )

    # is the service stopping?
    if scheduler_data.dynamic_sidecar.service_removal_state.can_remove:
        return RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.STOPPING,
            service_message=scheduler_data.dynamic_sidecar.status.info,
        )

    # the service should be either running or starting
    try:
        sidecar_state, sidecar_message = await get_dynamic_sidecar_state(
            # the service_name is unique and will not collide with other names
            # it can be used in place of the service_id here, as the docker API accepts both
            service_id=scheduler_data.service_name
        )
    except DockerServiceNotFoundError:
        # in this case, the service is starting, so state is pending
        return RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.PENDING,
            service_message=scheduler_data.dynamic_sidecar.status.info,
        )

    # while the dynamic-sidecar state is not RUNNING report it's state
    if sidecar_state != ServiceState.RUNNING:
        return RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=sidecar_state,
            service_message=sidecar_message,
        )

    # NOTE: This will be repeatedly called until the
    # user services are effectively started

    # wait for containers to start
    if len(scheduler_data.dynamic_sidecar.containers_inspect) == 0:
        # marks status as waiting for containers
        return RunningDynamicServiceDetails.from_scheduler_data(
            node_uuid=scheduler_data.node_uuid,
            scheduler_data=scheduler_data,
            service_state=ServiceState.STARTING,
            service_message="",
        )

    # compute composed containers states
    container_state, container_message = extract_containers_minimum_statuses(
        scheduler_data.dynamic_sidecar.containers_inspect
    )
    return RunningDynamicServiceDetails.from_scheduler_data(
        node_uuid=scheduler_data.node_uuid,
        scheduler_data=scheduler_data,
        service_state=container_state,
        service_message=container_message,
    )
