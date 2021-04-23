import logging
import traceback

# pylint: disable=redefined-builtin
from typing import Any, Dict, Optional, Union

import aiodocker
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_shared_store
from ..shared_store import SharedStore
from ..utils import docker_client

logger = logging.getLogger(__name__)

containers_router = APIRouter(tags=["containers"])


@containers_router.get(
    "/containers:inspect",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Erros in container"}
    },
)
async def containers_inspect(
    shared_store: SharedStore = Depends(get_shared_store),
) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """
    with docker_client() as docker:
        results = {}

        for container in shared_store.container_names:
            try:
                container_instance = await docker.containers.get(container)
                results[container] = await container_instance.show()
            except aiodocker.exceptions.DockerError as err:
                logger.warning(
                    "An unexpected Docker error occurred:\n%s",
                    str(traceback.format_exc()),
                )
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
                ) from err

        return results


@containers_router.get(
    "/containers",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Errors in container"}
    },
)
async def containers_docker_status(
    shared_store: SharedStore = Depends(get_shared_store),
) -> Dict[str, Any]:
    """ Returns the status of the containers """

    with docker_client() as docker:
        container_names = shared_store.container_names

        # if containers are being pulled, return pulling (fake status)
        if shared_store.is_pulling_containers:
            # pulling is a fake state use to share more information with the frontend
            return {x: {"Status": "pulling", "Error": ""} for x in container_names}

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
            except aiodocker.exceptions.DockerError as err:
                logger.warning(
                    "An unexpected Docker error occurred:\n%s",
                    str(traceback.format_exc()),
                )
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
                ) from err

        return results


@containers_router.get(
    "/containers/{id}:logs",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Container does not exists"
        }
    },
)
async def get_container_logs(
    id: str,
    since: int = Query(
        0,
        title="Timestamp",
        description="Only return logs since this time, as a UNIX timestamp",
    ),
    until: int = Query(
        0,
        title="Timestamp",
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
        message = f"No container '{id}' was started. Started containers '{shared_store.container_names}'"
        logger.warning(message)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    with docker_client() as docker:
        try:
            container_instance = await docker.containers.get(id)

            args = dict(stdout=True, stderr=True)
            if timestamps:
                args["timestamps"] = True

            if since or until:
                raise HTTPException(
                    status.HTTP_501_NOT_IMPLEMENTED,
                    detail="since and until options are still not implemented",
                )

            container_logs: str = await container_instance.log(**args)
            return container_logs
        except aiodocker.exceptions.DockerError as err:
            logger.warning(
                "An unexpected Docker error occurred:\n%s", str(traceback.format_exc())
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
            ) from err


@containers_router.get(
    "/containers/{id}:inspect",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Container does not exist"
        }
    },
)
async def inspect_container(
    id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """

    if id not in shared_store.container_names:
        message = f"No container '{id}' was started. Started containers '{shared_store.container_names}'"
        logger.warning(message)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    with docker_client() as docker:
        try:
            container_instance = await docker.containers.get(id)
            inspect_result: Dict[str, Any] = await container_instance.show()
            return inspect_result
        except aiodocker.exceptions.DockerError as err:
            logger.warning(
                "An unexpected Docker error occurred:\n%s", str(traceback.format_exc())
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
            ) from err


@containers_router.delete(
    "/containers/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Container does not exist"
        }
    },
)
async def remove_container(
    id: str, shared_store: SharedStore = Depends(get_shared_store)
) -> Optional[Dict[str, Any]]:
    if id not in shared_store.container_names:
        message = f"No container '{id}' was started. Started containers '{shared_store.container_names}'"
        logger.warning(message)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    with docker_client() as docker:
        try:
            container_instance = await docker.containers.get(id)
            await container_instance.delete()
            return None
        except aiodocker.exceptions.DockerError as err:
            logger.warning(
                "An unexpected Docker error occurred:\n%s", str(traceback.format_exc())
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err.message
            ) from err


__all__ = ["containers_router"]
