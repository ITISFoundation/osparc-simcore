from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from .._models import SchedulerServiceStatus
from ._docker import get_services_presence
from ._status_legacy import get_from_legacy_service
from ._status_new_style import ServiceSnapshot, get_from_new_style_service
from ._status_user_services import get_user_services_presence


async def get_scheduler_service_status(app: FastAPI, node_id: NodeID) -> SchedulerServiceStatus:
    services_presence = await get_services_presence(app, node_id)

    if services_presence is None:
        return SchedulerServiceStatus.IS_ABSENT

    if services_presence.legacy:
        return get_from_legacy_service(services_presence.legacy)

    if services_presence.dy_sidecar and services_presence.dy_proxy:
        return get_from_new_style_service(
            ServiceSnapshot(
                sidecar=services_presence.dy_sidecar,
                proxy=services_presence.dy_proxy,
                user_services=await get_user_services_presence(app, node_id),
            )
        )

    msg = f"Unexpected case for {services_presence=}"
    raise RuntimeError(msg)
