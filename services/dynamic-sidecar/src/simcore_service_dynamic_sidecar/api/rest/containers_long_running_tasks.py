from textwrap import dedent
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from models_library.api_schemas_directorv2.dynamic_services import ContainersCreate
from servicelib.fastapi.long_running_tasks._manager import FastAPILongRunningManager
from servicelib.fastapi.long_running_tasks.server import get_long_running_manager
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from servicelib.long_running_tasks.models import TaskId

from ...services import containers_long_running_tasks

router = APIRouter()


@router.post(
    "/containers/images:pull",
    summary="Pulls all the docker container images for the user services",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def pull_container_images(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.pull_container_images(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers",
    summary=dedent(
        """
        Starts the containers as defined in ContainerCreate by:
        - cleaning up resources from previous runs if any
        - starting the containers

        Progress may be obtained through URL
        Process may be cancelled through URL
        """
    ).strip(),
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def create_containers(  # pylint: disable=too-many-arguments
    request: Request,
    containers_create: ContainersCreate,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.create_containers(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        containers_create,
    )


@router.post(
    "/containers:down",
    summary="Remove the previously started containers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def down_containers(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.down_containers(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/state:restore",
    summary="Restores the state of the dynamic service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def restore_cotnainers_state(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.restore_cotnainers_state(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/state:save",
    summary="Stores the state of the dynamic service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def save_containers_state(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.save_containers_state(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/ports/inputs:pull",
    summary="Pull input ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def pull_container_port_inputs(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
    port_keys: list[str] | None = None,
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.pull_container_port_inputs(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace, port_keys
    )


@router.post(
    "/containers/ports/outputs:pull",
    summary="Pull output ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def pull_container_port_outputs(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
    port_keys: list[str] | None = None,
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.pull_container_port_outputs(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace, port_keys
    )


@router.post(
    "/containers/ports/outputs:push",
    summary="Push output ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def push_container_port_outputs(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.push_container_port_outputs(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers:restart",
    summary="Restarts previously started containers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def restart_containers(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.restart_containers(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )
