import logging

from .....models.schemas.dynamic_services import DynamicSidecarStatus, SchedulerData

logger = logging.getLogger(__name__)


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
        logger.warning(
            "Service waiting for manual intervention %s", scheduler_data.node_uuid
        )
    return service_awaits_intervention
