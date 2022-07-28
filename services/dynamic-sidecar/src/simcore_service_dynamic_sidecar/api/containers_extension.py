import logging

from aiodocker.networks import DockerNetwork
from fastapi import APIRouter, Depends, FastAPI
from fastapi import Path as PathParam
from fastapi import Request, Response, status
from models_library.services import ServiceOutput
from pydantic.main import BaseModel
from simcore_sdk.node_ports_v2.port_utils import is_file_type

from ..core.docker_utils import docker_client
from ..core.rabbitmq import RabbitMQ
from ..modules import directory_watcher
from ..modules.mounted_fs import MountedVolumes
from ._dependencies import get_application, get_mounted_volumes

logger = logging.getLogger(__name__)


class CreateDirsRequestItem(BaseModel):
    outputs_labels: dict[str, ServiceOutput]


class PatchDirectoryWatcherItem(BaseModel):
    is_enabled: bool


class _BaseNetworkItem(BaseModel):
    network_id: str


class AttachContainerToNetworkItem(_BaseNetworkItem):
    network_aliases: list[str]


class DetachContainerFromNetworkItem(_BaseNetworkItem):
    pass


async def send_message(rabbitmq: RabbitMQ, message: str) -> None:
    logger.info(message)
    await rabbitmq.post_log_message(f"[sidecar] {message}")


#
# HANDLERS ------------------
#
# - ANE: importing the `containers_router` router from .containers
# and generating the openapi spec, will not add the below entrypoints
# we need to create a new one in order for all the APIs to be
# detected as before
#
containers_router_extension = APIRouter(tags=["containers"])


@containers_router_extension.patch(
    "/containers/directory-watcher",
    summary="Enable/disable directory-watcher event propagation",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def toggle_directory_watcher(
    patch_directory_watcher_item: PatchDirectoryWatcherItem,
    app: FastAPI = Depends(get_application),
) -> None:
    if patch_directory_watcher_item.is_enabled:
        directory_watcher.enable_directory_watcher(app)
    else:
        directory_watcher.disable_directory_watcher(app)


@containers_router_extension.post(
    "/containers/ports/outputs/dirs",
    summary=(
        "Creates the output directories declared by the docker images's labels. "
        "It is more convenient to pass the labels from director-v2, "
        "since it already has all the machinery to call into director-v0 "
        "to retrieve them."
    ),
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def create_output_dirs(
    request_mode: CreateDirsRequestItem,
    mounted_volumes: MountedVolumes = Depends(get_mounted_volumes),
) -> None:
    outputs_path = mounted_volumes.disk_outputs_path
    for port_key, service_output in request_mode.outputs_labels.items():
        if is_file_type(service_output.property_type):
            dir_to_create = outputs_path / port_key
            dir_to_create.mkdir(parents=True, exist_ok=True)


@containers_router_extension.post(
    "/containers/{id}/networks:attach",
    summary="attach container to a network, if not already attached",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def attach_container_to_network(
    request: Request,
    item: AttachContainerToNetworkItem,
    container_id: str = PathParam(..., alias="id"),
) -> None:
    assert request  # nosec

    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = {
            x["NetworkID"]
            for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if item.network_id in attached_network_ids:
            logger.info(
                "Container %s already attached to network %s",
                container_id,
                item.network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=item.network_id)
        await network.connect(
            {
                "Container": container_id,
                "EndpointConfig": {"Aliases": item.network_aliases},
            }
        )


@containers_router_extension.post(
    "/containers/{id}/networks:detach",
    summary="detach container from a network, if not already detached",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_container_from_network(
    item: DetachContainerFromNetworkItem,
    container_id: str = PathParam(..., alias="id"),
) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = {
            x["NetworkID"]
            for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if item.network_id not in attached_network_ids:
            logger.info(
                "Container %s already detached from network %s",
                container_id,
                item.network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=item.network_id)
        await network.disconnect({"Container": container_id})
