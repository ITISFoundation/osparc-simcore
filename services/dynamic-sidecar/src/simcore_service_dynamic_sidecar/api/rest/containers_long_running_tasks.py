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
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def pull_container_images(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
) -> TaskId:
    """Pulls all the docker container images for the user services"""
    _ = request
    return await containers_long_running_tasks.pull_user_services_images(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post("/containers", status_code=status.HTTP_202_ACCEPTED, response_model=TaskId)
@cancel_on_disconnect
async def create_containers(  # pylint: disable=too-many-arguments
    request: Request,
    containers_create: ContainersCreate,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
) -> TaskId:
    """
    Starts the containers as defined in ContainerCreate by:
    - cleaning up resources from previous runs if any
    - starting the containers

    Progress may be obtained through URL
    Process may be cancelled through URL
    """
    _ = request
    return await containers_long_running_tasks.create_user_services(
        long_running_manager.rpc_client,
        long_running_manager.lrt_namespace,
        containers_create,
    )


@router.post("/containers:down", status_code=status.HTTP_202_ACCEPTED, response_model=TaskId)
@cancel_on_disconnect
async def down_containers(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
) -> TaskId:
    """Remove the previously started containers"""
    _ = request
    return await containers_long_running_tasks.remove_user_services(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/state:restore",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def restore_containers_state_paths(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
) -> TaskId:
    """Restores the state of the dynamic service"""
    _ = request
    return await containers_long_running_tasks.restore_user_services_state_paths(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/state:save",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def save_containers_state_paths(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
) -> TaskId:
    """Stores the state of the dynamic service"""
    _ = request
    return await containers_long_running_tasks.save_user_services_state_paths(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/ports/inputs:pull",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def pull_container_port_inputs(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
    port_keys: list[str] | None = None,
) -> TaskId:
    """Pull input ports data"""
    _ = request
    return await containers_long_running_tasks.pull_user_services_input_ports(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace, port_keys
    )


@router.post(
    "/containers/ports/outputs:pull",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def pull_container_port_outputs(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
    port_keys: list[str] | None = None,
) -> TaskId:
    """Pull output ports data"""
    _ = request
    return await containers_long_running_tasks.pull_user_services_output_ports(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace, port_keys
    )


@router.post(
    "/containers/ports/outputs:push",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def push_container_port_outputs(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
) -> TaskId:
    """Push output ports data"""
    _ = request
    return await containers_long_running_tasks.push_user_services_output_ports(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers:restart",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def restart_containers(
    request: Request,
    long_running_manager: Annotated[FastAPILongRunningManager, Depends(get_long_running_manager)],
) -> TaskId:
    """Restarts previously started user services"""
    _ = request
    return await containers_long_running_tasks.restart_user_services(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )
