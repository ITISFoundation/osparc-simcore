import logging

from aiodocker.networks import DockerNetwork
from fastapi import FastAPI
from models_library.services import ServiceOutput
from simcore_sdk.node_ports_v2.port_utils import is_file_type

from ..core.docker_utils import docker_client
from ..modules.inputs import disable_inputs_pulling, enable_inputs_pulling
from ..modules.mounted_fs import MountedVolumes
from ..modules.outputs import (
    OutputsContext,
    disable_event_propagation,
    enable_event_propagation,
)

_logger = logging.getLogger(__name__)


async def toggle_ports_io(
    app: FastAPI, *, enable_outputs: bool, enable_inputs: bool
) -> None:
    if enable_outputs:
        await enable_event_propagation(app)
    else:
        await disable_event_propagation(app)

    if enable_inputs:
        enable_inputs_pulling(app)
    else:
        disable_inputs_pulling(app)


async def create_output_dirs(
    app: FastAPI, *, outputs_labels: dict[str, ServiceOutput]
) -> None:
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    outputs_context: OutputsContext = app.state.outputs_context

    outputs_path = mounted_volumes.disk_outputs_path
    file_type_port_keys = []
    non_file_port_keys = []
    for port_key, service_output in outputs_labels.items():
        _logger.debug("Parsing output labels, detected: %s", f"{port_key=}")
        if is_file_type(service_output.property_type):
            dir_to_create = outputs_path / port_key
            dir_to_create.mkdir(parents=True, exist_ok=True)
            file_type_port_keys.append(port_key)
        else:
            non_file_port_keys.append(port_key)

    _logger.debug(
        "Setting: %s, %s", f"{file_type_port_keys=}", f"{non_file_port_keys=}"
    )
    await outputs_context.set_file_type_port_keys(file_type_port_keys)
    outputs_context.non_file_type_port_keys = non_file_port_keys


async def attach_container_to_network(
    *, container_id: str, network_id: str, network_aliases: list[str]
) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = {
            x["NetworkID"]
            for x in container_inspect["NetworkSettings"]["Networks"].values()
        }

        if network_id in attached_network_ids:
            _logger.debug(
                "Container %s already attached to network %s",
                container_id,
                network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=network_id)
        await network.connect(
            {
                "Container": container_id,
                "EndpointConfig": {"Aliases": network_aliases},
            }
        )


async def detach_container_from_network(*, container_id: str, network_id: str) -> None:
    async with docker_client() as docker:
        container_instance = await docker.containers.get(container_id)
        container_inspect = await container_instance.show()

        attached_network_ids: set[str] = set(
            container_inspect["NetworkSettings"]["Networks"].keys()
        )

        if network_id not in attached_network_ids:
            _logger.debug(
                "Container %s already detached from network %s",
                container_id,
                network_id,
            )
            return

        # NOTE: A docker network is only visible on a docker node when it is
        # used by a container
        network = DockerNetwork(docker=docker, id_=network_id)
        await network.disconnect({"Container": container_id, "Force": True})
