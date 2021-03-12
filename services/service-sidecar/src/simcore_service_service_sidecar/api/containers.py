from typing import Any, Dict, List

import aiodocker
from fastapi import APIRouter, Request, Response

containers_router = APIRouter()


@containers_router.get("/containers")
async def get_spawned_container_names(request: Request) -> List[str]:
    """ Returns a list of containers created using docker-compose """
    return request.app.state.shared_store.get_container_names()


@containers_router.get("/containers:inspect")
async def containers_inspect(request: Request, response: Response) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """
    docker = aiodocker.Docker()

    container_names = request.app.state.shared_store.get_container_names()
    container_names = container_names if container_names else {}

    results = {}

    for container in container_names:
        try:
            container_instance = await docker.containers.get(container)
            results[container] = await container_instance.show()
        except aiodocker.exceptions.DockerError as e:
            response.status_code = 400
            return dict(error=e.message)

    return results


__all__ = ["containers_router"]
