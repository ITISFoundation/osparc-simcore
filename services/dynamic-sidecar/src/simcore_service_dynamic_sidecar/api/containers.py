# pylint: disable=redefined-builtin
from typing import Any, Dict, List, Union

import aiodocker
from fastapi import APIRouter, Depends, Query, Request, Response
from starlette.status import HTTP_400_BAD_REQUEST

from ..dependencies import get_shared_store
from ..shared_store import SharedStore

containers_router = APIRouter(tags=["containers"])


@containers_router.get("/containers")
async def get_spawned_container_names(request: Request) -> List[str]:
    """ Returns a list of containers created using docker-compose """
    shared_store: SharedStore = request.app.state.shared_store
    return shared_store.container_names


@containers_router.get("/containers:inspect")
async def containers_inspect(
    response: Response, shared_store: SharedStore = Depends(get_shared_store)
) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """
    docker = aiodocker.Docker()

    container_names = (
        shared_store.container_names if shared_store.container_names else {}
    )

    results = {}

    for container in container_names:
        try:
            container_instance = await docker.containers.get(container)
            results[container] = await container_instance.show()
        except aiodocker.exceptions.DockerError as e:
            response.status_code = HTTP_400_BAD_REQUEST
            return dict(error=e.message)

    return results


@containers_router.get("/containers:docker-status")
async def containers_docker_status(
    response: Response, shared_store: SharedStore = Depends(get_shared_store)
) -> Dict[str, Any]:
    """ Returns the status of the containers """

    def assemble_entry(status: str, error: str = "") -> Dict[str, str]:
        return {"Status": status, "Error": error}

    docker = aiodocker.Docker()

    container_names = (
        shared_store.container_names if shared_store.container_names else {}
    )

    # if containers are being pulled, return pulling (fake status)
    if shared_store.is_pulling_containsers:
        # pulling is a fake state use to share more information with the frontend
        return {x: assemble_entry(status="pulling") for x in container_names}

    results = {}

    for container in container_names:
        try:
            container_instance = await docker.containers.get(container)
            container_inspect = await container_instance.show()
            container_state = container_inspect.get("State", {})

            # pending is another fake state use to share more information with the frontend
            results[container] = {
                "Status": container_state.get("Status", "pending"),
                "Error": container_state.get("Error", ""),
            }
        except aiodocker.exceptions.DockerError as e:
            response.status_code = HTTP_400_BAD_REQUEST
            return dict(error=e.message)

    return results


@containers_router.get("/containers/{id}/logs")
async def get_container_logs(
    # pylint: disable=unused-argument
    response: Response,
    id: str,
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
    shared_store: SharedStore = Depends(get_shared_store),
) -> Union[str, Dict[str, Any]]:
    """ Returns the logs of a given container if found """
    # TODO: remove from here and dump directly into the logs of this service
    # do this in PR#1887

    if id not in shared_store.container_names:
        response.status_code = HTTP_400_BAD_REQUEST
        return dict(error=f"No container '{id}' was started")

    docker = aiodocker.Docker()

    try:
        container_instance = await docker.containers.get(id)

        args = dict(stdout=True, stderr=True)
        if timestamps:
            args["timestamps"] = True

        container_logs: str = await container_instance.log(**args)
        return container_logs
    except aiodocker.exceptions.DockerError as e:
        response.status_code = HTTP_400_BAD_REQUEST
        return dict(error=e.message)


@containers_router.get("/containers/{id}/inspect")
async def inspect_container(
    response: Response, id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """

    if id not in shared_store.container_names:
        response.status_code = HTTP_400_BAD_REQUEST
        return dict(error=f"No container '{id}' was started")

    docker = aiodocker.Docker()

    try:
        container_instance = await docker.containers.get(id)
        inspect_result: Dict[str, Any] = await container_instance.show()
        return inspect_result
    except aiodocker.exceptions.DockerError as e:
        response.status_code = HTTP_400_BAD_REQUEST
        return dict(error=e.message)


@containers_router.delete("/containers/{id}/remove")
async def remove_container(
    response: Response, id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> Union[bool, Dict[str, Any]]:

    if id not in shared_store.container_names:
        response.status_code = HTTP_400_BAD_REQUEST
        return dict(error=f"No container '{id}' was started")

    docker = aiodocker.Docker()

    try:
        container_instance = await docker.containers.get(id)
        await container_instance.delete()
        return True
    except aiodocker.exceptions.DockerError as e:
        response.status_code = HTTP_400_BAD_REQUEST
        return dict(error=e.message)


__all__ = ["containers_router"]
