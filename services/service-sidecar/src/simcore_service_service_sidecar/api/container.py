from typing import Dict, Any
import aiodocker

from fastapi import APIRouter, Response, Query, Request

from ..settings import ServiceSidecarSettings

container_router = APIRouter()


@container_router.get("/container/logs")
async def get_container_logs(
    # pylint: disable=unused-argument
    request: Request,
    response: Response,
    container: str,
    since: int = Query(
        0,
        title="Timstamp",
        description="Only return logs since this time, as a UNIX timestamp",
    ),
    until: int = Query(
        0,
        title="Timstamp",
        description="Only return logs before this time, as a UNIX timestamp",
    ),
    timestamps: bool = Query(
        False,
        title="Display timestamps",
        description="Enabling this parameter will include timestamps in logs",
    ),
) -> str:
    """ Returns the logs of a given container if found """
    settings: ServiceSidecarSettings = request.app.state.settings

    if container not in settings.async_store.get_container_names():
        response.status_code = 400
        return f"No container '{container}' was started"

    docker = aiodocker.Docker()

    try:
        container_instance = await docker.containers.get(container)

        args = dict(stdout=True, stderr=True)
        if timestamps:
            args["timestamps"] = True

        return await container_instance.log(**args)
    except aiodocker.exceptions.DockerError as e:
        response.status_code = 400
        return e.message


@container_router.get("/container/inspect")
async def container_inspect(
    request: Request, response: Response, container: str
) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """
    settings: ServiceSidecarSettings = request.app.state.settings

    if container not in settings.async_store.get_container_names():
        response.status_code = 400
        return dict(error=f"No container '{container}' was started")

    docker = aiodocker.Docker()

    try:
        container_instance = await docker.containers.get(container)
        return await container_instance.show()
    except aiodocker.exceptions.DockerError as e:
        response.status_code = 400
        return dict(error=e.message)


__all__ = ["container_router"]