from typing import Annotated

from aiodocker import Docker
from fastapi import APIRouter, Depends, status
from models_library.docker import DockerServiceID
from models_library.generated_models.docker_rest_api import ServiceSpec

from ..dependencies.docker import get_shared_docker_client

router = APIRouter()


def _envs_to_dict(data: list | dict) -> dict:
    if isinstance(data, dict):
        return data

    result = {}
    for item in data:
        key, value = item.split("=", 1)
        result[key] = value

    return result


@router.post("/", summary="create a docker service", status_code=status.HTTP_200_OK)
async def create_docker_service(
    service_spec: ServiceSpec,
    shared_docker_client: Annotated[Docker, Depends(get_shared_docker_client)],
) -> DockerServiceID:
    params = service_spec.model_dump(mode="json", by_alias=True)

    if (
        "ContainerSpec" in params["TaskTemplate"]
        and "Env" in params["TaskTemplate"]["ContainerSpec"]
    ):
        params["TaskTemplate"]["ContainerSpec"]["Env"] = _envs_to_dict(
            params["TaskTemplate"]["ContainerSpec"]["Env"]
        )

    created_service = await shared_docker_client.services.create(
        task_template=params["TaskTemplate"],
        name=params["Name"],
        labels=params["Labels"],
        mode=params["Mode"],
        update_config=params["UpdateConfig"],
        rollback_config=params["RollbackConfig"],
        networks=params["Networks"],
        endpoint_spec=params["EndpointSpec"],
    )
    return DockerServiceID(created_service["ID"])


@router.delete(
    "/{service_id}",
    summary="removes an existing docker service",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_docker_service(
    service_id: DockerServiceID,
    shared_docker_client: Annotated[Docker, Depends(get_shared_docker_client)],
):
    await shared_docker_client.services.delete(service_id)
