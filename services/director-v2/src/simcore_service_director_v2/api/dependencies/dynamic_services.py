import logging

from fastapi import Depends, Request
from models_library.projects_nodes import NodeID
from servicelib.logging_utils import log_decorator
from starlette.datastructures import URL

from ...core.settings import DynamicServicesSettings
from ...models.schemas.dynamic_services import RunningDynamicServiceDetails
from ...modules.director_v0 import DirectorV0Client
from ...modules.dynamic_services import ServicesClient
from ...modules.dynamic_sidecar.scheduler import DynamicSidecarsScheduler
from .director_v0 import get_director_v0_client

logger = logging.getLogger(__name__)


@log_decorator(logger=logger)
async def get_service_base_url(
    node_uuid: NodeID,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> URL:
    # get the service details
    service_details: RunningDynamicServiceDetails = (
        await director_v0_client.get_running_service_details(node_uuid)
    )
    return URL(service_details.legacy_service_url)


@log_decorator(logger=logger)
def get_services_client(request: Request) -> ServicesClient:
    return ServicesClient.instance(request.app)


def get_dynamic_services_settings(request: Request) -> DynamicServicesSettings:
    settings: DynamicServicesSettings = request.app.state.settings.DYNAMIC_SERVICES
    return settings


def get_scheduler(request: Request) -> DynamicSidecarsScheduler:
    scheduler: DynamicSidecarsScheduler = request.app.state.dynamic_sidecar_scheduler
    return scheduler
