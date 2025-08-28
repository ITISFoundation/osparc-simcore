from fastapi import FastAPI
from models_library.services import ServiceOutput
from servicelib.rabbitmq import RPCRouter

from ...services import container_extensions

router = RPCRouter()


@router.expose()
async def toggle_ports_io(
    app: FastAPI, *, enable_outputs: bool, enable_inputs: bool
) -> None:
    await container_extensions.toggle_ports_io(
        app, enable_outputs=enable_outputs, enable_inputs=enable_inputs
    )


@router.expose()
async def create_output_dirs(
    app: FastAPI, *, outputs_labels: dict[str, ServiceOutput]
) -> None:
    await container_extensions.create_output_dirs(app, outputs_labels=outputs_labels)


@router.expose()
async def attach_container_to_network(
    app: FastAPI, *, container_id: str, network_id: str, network_aliases: list[str]
) -> None:
    _ = app
    await container_extensions.attach_container_to_network(
        container_id=container_id,
        network_id=network_id,
        network_aliases=network_aliases,
    )


@router.expose()
async def detach_container_from_network(
    app: FastAPI, *, container_id: str, network_id: str
) -> None:
    _ = app
    await container_extensions.detach_container_from_network(
        container_id=container_id, network_id=network_id
    )
