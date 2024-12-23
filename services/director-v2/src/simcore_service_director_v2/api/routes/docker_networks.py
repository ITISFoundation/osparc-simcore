from typing import Annotated

from aiodocker import Docker
from fastapi import APIRouter, Depends, status
from models_library.docker import DockerNetworkID
from models_library.generated_models.docker_rest_api import Network

from ..dependencies.docker import get_shared_docker_client

router = APIRouter()


@router.post(
    "/",
    summary="create a docker network given the input parameters",
    status_code=status.HTTP_200_OK,
)
async def create_docker_network(
    docker_network: Network,
    shared_docker_client: Annotated[Docker, Depends(get_shared_docker_client)],
) -> DockerNetworkID:
    created_network = await shared_docker_client.networks.create(
        docker_network.model_dump(mode="json")
    )
    return created_network.id


@router.delete(
    "/{network_id}",
    summary="removes an existing docker network",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_docker_network(
    network_id: DockerNetworkID,
    shared_docker_client: Annotated[Docker, Depends(get_shared_docker_client)],
):
    created_network = await shared_docker_client.networks.get(network_id)
    await created_network.delete()
