from fastapi import Depends, Request
from models_library.projects_nodes import NodeID
from starlette.datastructures import URL

from ...models.schemas.services import RunningServiceType
from ...modules.dynamic_services_v0 import ServicesV0Client
from .director_v0 import DirectorV0Client, get_director_v0_client


async def get_services_v0_client(
    node_uuid: NodeID,
    request: Request,
    director_v0_client: DirectorV0Client = Depends(get_director_v0_client),
) -> ServicesV0Client:

    # get the service details
    service_details: RunningServiceType = (
        await director_v0_client.get_running_service_details(node_uuid)
    )

    # compute service url
    service_url = URL(
        f"{service_details.service_host}:{service_details.service_port}{service_details.service_basepath}"
    )

    client = ServicesV0Client.instance(request.app)
    return client
