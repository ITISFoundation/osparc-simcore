from fastapi import FastAPI
from models_library.projects_nodes_io import StorageFileID
from models_library.services import ServiceOutput
from servicelib.rabbitmq import RPCRouter

from ...services import container_extensions

router = RPCRouter()


@router.expose()
async def toggle_ports_io(app: FastAPI, *, enable_outputs: bool, enable_inputs: bool) -> None:
    """Enable/disable ports i/o"""
    await container_extensions.toggle_ports_io(app, enable_outputs=enable_outputs, enable_inputs=enable_inputs)


@router.expose()
async def create_output_dirs(app: FastAPI, *, outputs_labels: dict[str, ServiceOutput]) -> None:
    """
    Creates the output directories declared by the docker images's labels.
    It is more convenient to pass the labels from director-v2,
    since it already has all the machinery to call into director-v0
    to retrieve them.
    """
    await container_extensions.create_output_dirs(app, outputs_labels=outputs_labels)


@router.expose()
async def attach_container_to_network(
    app: FastAPI, *, container_id: str, network_id: str, network_aliases: list[str]
) -> None:
    """attach container to a network, if not already attached"""
    _ = app
    await container_extensions.attach_container_to_network(
        container_id=container_id,
        network_id=network_id,
        network_aliases=network_aliases,
    )


@router.expose()
async def detach_container_from_network(app: FastAPI, *, container_id: str, network_id: str) -> None:
    """detach container from a network, if not already detached"""
    _ = app
    await container_extensions.detach_container_from_network(container_id=container_id, network_id=network_id)


@router.expose()
async def refresh_containers_files(app: FastAPI, *, s3_directory: StorageFileID, recursive: bool) -> None:
    """refresh directory content from s3, if data is mounted from S3"""
    await container_extensions.refresh_containers_files(app=app, s3_directory=s3_directory, recursive=recursive)
