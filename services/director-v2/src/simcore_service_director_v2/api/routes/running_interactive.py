# pylint: disable=unused-argument

from fastapi import APIRouter, Depends, Query, status

from ...models.constants import SERVICE_IMAGE_NAME_RE, VERSION_RE
from ...models.schemas.services import RunningServicesEnveloped
from ..dependencies.director_v0 import ReverseProxyClient, get_reverse_proxy_to_v0

router = APIRouter()


UserIdQuery = Query(
    ...,
    description="The ID of the user that starts the service",
)
ProjectIdQuery = Query(
    ..., description="The ID of the project in which the service starts"
)


@router.get(
    "",
    description="Lists of running interactive services",
    response_model=RunningServicesEnveloped,
)
async def list_running_interactive_services(
    user_id: str = UserIdQuery,
    project_id: str = ProjectIdQuery,
    director_v0: ReverseProxyClient = Depends(get_reverse_proxy_to_v0),
):
    return director_v0.request(user_id, project_id)


@router.post(
    "",
    description="Starts an interactive service in the  platform",
    status_code=status.HTTP_201_CREATED,
)
async def start_interactive_service(
    user_id: str = UserIdQuery,
    project_id: str = ProjectIdQuery,
    service_key: str = Query(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=SERVICE_IMAGE_NAME_RE,
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    ),
    service_version: str = Query(
        ...,
        description="The tag/version of the service",
        regex=VERSION_RE,
        example="1.0.0",
    ),
    service_uuid: str = Query(..., description="The uuid to assign the service with"),
    service_base_path: str = Query(
        "",
        description="predefined basepath for the backend service otherwise uses root",
        example="/x/EycCXbU0H/",
    ),
    director_v0: ReverseProxyClient = Depends(get_reverse_proxy_to_v0),
):
    return director_v0.request(
        user_id,
        project_id,
        service_key,
        service_version,
        service_uuid,
        service_base_path,
    )
