from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi import Path as PathParam
from fastapi import Request, Response, status
from models_library.services import ServiceOutput
from pydantic.main import BaseModel

from ...services import container_extensions
from ._dependencies import get_application


class CreateDirsRequestItem(BaseModel):
    outputs_labels: dict[str, ServiceOutput]


class PatchPortsIOItem(BaseModel):
    enable_outputs: bool
    enable_inputs: bool


class _BaseNetworkItem(BaseModel):
    network_id: str


class AttachContainerToNetworkItem(_BaseNetworkItem):
    network_aliases: list[str]


class DetachContainerFromNetworkItem(_BaseNetworkItem):
    pass


#
# HANDLERS ------------------
#
router = APIRouter()


@router.patch(
    "/containers/ports/io",
    summary="Enable/disable ports i/o",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def toggle_ports_io(
    patch_ports_io_item: PatchPortsIOItem,
    app: Annotated[FastAPI, Depends(get_application)],
) -> None:
    await container_extensions.toggle_ports_io(
        app,
        enable_outputs=patch_ports_io_item.enable_outputs,
        enable_inputs=patch_ports_io_item.enable_inputs,
    )


@router.post(
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
    app: Annotated[FastAPI, Depends(get_application)],
) -> None:
    await container_extensions.create_output_dirs(
        app, outputs_labels=request_mode.outputs_labels
    )


@router.post(
    "/containers/{id}/networks:attach",
    summary="attach container to a network, if not already attached",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def attach_container_to_network(
    request: Request,
    item: AttachContainerToNetworkItem,
    container_id: Annotated[str, PathParam(..., alias="id")],
) -> None:
    assert request  # nosec
    await container_extensions.attach_container_to_network(
        container_id=container_id,
        network_id=item.network_id,
        network_aliases=item.network_aliases,
    )


@router.post(
    "/containers/{id}/networks:detach",
    summary="detach container from a network, if not already detached",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_container_from_network(
    item: DetachContainerFromNetworkItem,
    container_id: Annotated[str, PathParam(..., alias="id")],
) -> None:
    await container_extensions.detach_container_from_network(
        container_id=container_id,
        network_id=item.network_id,
    )
