from typing import Any, Dict, List

import aiodocker
from fastapi import APIRouter, Request, Response

from ..shared_store import SharedStore

containers_router = APIRouter()


@containers_router.get("/containers")
async def get_spawned_container_names(request: Request) -> List[str]:
    """ Returns a list of containers created using docker-compose """
    shared_store: SharedStore = request.app.state.shared_store
    return shared_store.container_names


@containers_router.get("/containers:inspect")
async def containers_inspect(request: Request, response: Response) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """
    docker = aiodocker.Docker()

    shared_store: SharedStore = request.app.state.shared_store
    container_names = (
        shared_store.container_names if shared_store.container_names else {}
    )

    results = {}

    for container in container_names:
        try:
            container_instance = await docker.containers.get(container)
            results[container] = await container_instance.show()
        except aiodocker.exceptions.DockerError as e:
            response.status_code = 400
            return dict(error=e.message)

    return results


@containers_router.get("/containers:docker-status")
async def containers_docker_status(
    request: Request, response: Response
) -> Dict[str, Any]:
    """ Returns the status of the containers """

    def assemble_entry(status: str, error: str = "") -> Dict[str, str]:
        return {"Status": status, "Error": error}

    docker = aiodocker.Docker()

    shared_store = request.app.state.shared_store
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
            response.status_code = 400
            return dict(error=e.message)

    return results


__all__ = ["containers_router"]
