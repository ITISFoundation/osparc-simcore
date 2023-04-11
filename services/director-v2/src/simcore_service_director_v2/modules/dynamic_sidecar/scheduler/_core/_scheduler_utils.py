import logging
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.long_running_tasks.client import ProgressCallback

from .....models.schemas.dynamic_services import DynamicSidecarStatus, SchedulerData
from ...api_client import DynamicSidecarClient, get_dynamic_sidecar_client
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
