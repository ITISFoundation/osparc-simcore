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
async def pull_user_servcices_docker_images(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.pull_user_services_docker_images(
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
async def create_service_containers_task(  # pylint: disable=too-many-arguments
    request: Request,
    containers_create: ContainersCreate,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.create_service_containers_task(
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
async def runs_docker_compose_down_task(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.runs_docker_compose_down_task(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/state:restore",
    summary="Restores the state of the dynamic service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def state_restore_task(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.state_restore_task(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/state:save",
    summary="Stores the state of the dynamic service",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def state_save_task(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.state_save_task(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers/ports/inputs:pull",
    summary="Pull input ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def ports_inputs_pull_task(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
    port_keys: list[str] | None = None,
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.ports_inputs_pull_task(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace, port_keys
    )


@router.post(
    "/containers/ports/outputs:pull",
    summary="Pull output ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def ports_outputs_pull_task(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
    port_keys: list[str] | None = None,
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.ports_outputs_pull_task(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace, port_keys
    )


@router.post(
    "/containers/ports/outputs:push",
    summary="Push output ports data",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def ports_outputs_push_task(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.ports_outputs_push_task(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )


@router.post(
    "/containers:restart",
    summary="Restarts previously started containers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskId,
)
@cancel_on_disconnect
async def containers_restart_task(
    request: Request,
    long_running_manager: Annotated[
        FastAPILongRunningManager, Depends(get_long_running_manager)
    ],
) -> TaskId:
    _ = request
    return await containers_long_running_tasks.containers_restart_task(
        long_running_manager.rpc_client, long_running_manager.lrt_namespace
    )
