import logging
from copy import deepcopy

from fastapi import FastAPI

from ....core.settings import DynamicServicesSettings
from ....models.schemas.dynamic_services import SchedulerData
from ..docker_api import are_sidecar_and_proxy_services_present
from .events import REGISTERED_EVENTS

logger = logging.getLogger(__name__)


async def apply_observation_cycle(
    app: FastAPI, scheduler: "DynamicSidecarsScheduler", scheduler_data: SchedulerData
) -> None:
    """
    fetches status for service and then processes all the registered events
    and updates the status back
    """
    dynamic_services_settings: DynamicServicesSettings = (
        app.state.settings.DYNAMIC_SERVICES
    )
    # TODO: PC-> ANE: custom settings are frozen. in principle, no need to create copies.
    initial_status = deepcopy(scheduler_data.dynamic_sidecar.status)

    if (  # do not refactor, second part of "and condition" is skipped most times
        scheduler_data.dynamic_sidecar.were_containers_created
        and not await are_sidecar_and_proxy_services_present(
            node_uuid=scheduler_data.node_uuid,
            dynamic_sidecar_settings=dynamic_services_settings.DYNAMIC_SIDECAR,
        )
    ):
        # NOTE: once marked for removal the observation cycle needs
        # to continue in order for the service to be removed
        logger.warning(
            "Removing service %s from observation", scheduler_data.service_name
        )
        await scheduler.mark_service_for_removal(
            node_uuid=scheduler_data.node_uuid,
            can_save=scheduler_data.dynamic_sidecar.were_containers_created,
        )

    for dynamic_scheduler_event in REGISTERED_EVENTS:
        if await dynamic_scheduler_event.will_trigger(
            app=app, scheduler_data=scheduler_data
        ):
            # event.action will apply changes to the output_scheduler_data
            await dynamic_scheduler_event.action(app, scheduler_data)

    # check if the status of the services has changed from OK
    if initial_status != scheduler_data.dynamic_sidecar.status:
        logger.info(
            "Service %s overall status changed to %s",
            scheduler_data.service_name,
            scheduler_data.dynamic_sidecar.status,
        )
