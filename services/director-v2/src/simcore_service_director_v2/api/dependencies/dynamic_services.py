import logging

from fastapi import Depends, Request
from models_library.projects_nodes import NodeID
from starlette.datastructures import URL

from ...models.schemas.services import RunningServiceDetails
from ...modules.dynamic_services import ServicesClient
from ...utils.logging_utils import log_decorator
from .director_v0 import DirectorV0Client, get_director_v0_client

logger = logging.getLogger(__name__)


@log_decorator(logger=logger)
async def get_service_base_url(
    node_uuid: NodeID,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> URL:

    # get the service details
    service_details: RunningServiceDetails = (
        await director_v0_client.get_running_service_details(node_uuid)
    )
    # compute service url
    service_url = URL(
        f"http://{service_details.service_host}:{service_details.service_port}{service_details.service_basepath}"
    )
    return service_url


@log_decorator(logger=logger)
def get_services_client(
    request: Request,
) -> ServicesClient:

    client = ServicesClient.instance(request.app)
    return client
