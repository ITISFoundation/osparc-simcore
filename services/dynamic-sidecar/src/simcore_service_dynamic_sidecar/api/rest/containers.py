from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi import Path as PathParam
from models_library.api_schemas_directorv2.dynamic_services import ContainersComposeSpec
from models_library.api_schemas_dynamic_sidecar.containers import (
    ActivityInfoOrNone,
)
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

from ...services import containers
from ...services.containers import (
    ContainerIsMissingError,
    ContainerNotFoundError,
    InvalidFilterFormatError,
    MissingDockerComposeDownSpecError,
)

router = APIRouter()


@router.post(
    "/containers/compose-spec",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
@cancel_on_disconnect
async def create_compose_spec(
    request: Request, containers_compose_spec: ContainersComposeSpec
):
    """
    Validates and stores the docker compose spec for the user services.
    """
    _ = request

    await containers.create_compose_spec(
        app=request.app, containers_compose_spec=containers_compose_spec
    )


@router.get(
    "/containers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
@cancel_on_disconnect
async def containers_docker_inspect(
    request: Request,
    only_status: bool = Query(  # noqa: FBT001
        default=False, description="if True only show the status of the container"
    ),
) -> dict[str, Any]:
    """
    Returns entire docker inspect data, if only_state is True,
    the status of the containers is returned
    """
    _ = request
    return await containers.containers_docker_inspect(
        app=request.app, only_status=only_status
    )


@router.get("/containers/activity")
@cancel_on_disconnect
async def get_containers_activity(request: Request) -> ActivityInfoOrNone:
    """
    If user service declared an inactivity hook, this endpoint provides
    information about how much time has passed since the service became inactive.
    """
    _ = request
    return await containers.get_containers_activity(app=request.app)


@router.get(
    "/containers/name",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "No entrypoint container found or spec is not yet present"
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Filters could not be parsed"
        },
    },
)
@cancel_on_disconnect
async def get_containers_name(
    request: Request,
    filters: str = Query(
        ...,
        description=(
            "JSON encoded dictionary. FastAPI does not "
            "allow for dict as type in query parameters"
        ),
    ),
) -> str | dict[str, Any]:
    """
    Searches for the container's name given the network
    on which the proxy communicates with it.
    Supported filters:
        network: matches against the exact network name
            assigned to the container; `will include`
            containers
        exclude: matches if contained in the name of the
            container; `will exclude` containers
    """
    _ = request

    try:
        return await containers.get_containers_name(app=request.app, filters=filters)
    except InvalidFilterFormatError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{e}") from e
    except (MissingDockerComposeDownSpecError, ContainerNotFoundError) as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{e}") from e


@router.get(
    "/containers/{id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Container does not exist"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"},
    },
)
@cancel_on_disconnect
async def inspect_container(
    request: Request, container_id: str = PathParam(..., alias="id")
) -> dict[str, Any]:
    """Returns information about the container, like docker inspect command"""
    _ = request

    try:
        return await containers.inspect_container(
            app=request.app, container_id=container_id
        )
    except ContainerIsMissingError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{e}") from e
