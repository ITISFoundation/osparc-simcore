from fastapi import APIRouter, Query, status

from ...models.constants import SERVICE_IMAGE_NAME_RE, VERSION_RE
from ...models.schemas.services import RunningServicesEnveloped

router = APIRouter()


UserIdQuery = Query(..., description="The ID of the user that starts the service",)
ProjectIdQuery = Query(
    ..., description="The ID of the project in which the service starts"
)


@router.get(
    "",
    description="Lists of running interactive services",
    response_model=RunningServicesEnveloped,
)
async def list_running_interactive_services(
    user_id: str = UserIdQuery, project_id: str = ProjectIdQuery
):
    pass


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
        example=["1.0.0", "0.0.1"],
    ),
    service_uuid: str = Query(..., description="The uuid to assign the service with"),
    service_base_path: str = Query(
        "",
        description="predefined basepath for the backend service otherwise uses root",
        example="/x/EycCXbU0H/",
    ),
):
    pass
