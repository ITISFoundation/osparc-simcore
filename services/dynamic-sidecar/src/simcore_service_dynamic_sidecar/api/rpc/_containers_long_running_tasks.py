from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import ContainersCreate
from servicelib.long_running_tasks.models import LRTNamespace, TaskId
from servicelib.rabbitmq import RPCRouter

from ...core.rabbitmq import get_rabbitmq_rpc_client
from ...services import containers_long_running_tasks

router = RPCRouter()


@router.expose()
async def pull_user_services_docker_images_task(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.pull_user_services_docker_images(
        rpc_client, lrt_namespace
    )


@router.expose()
async def create_service_containers_task(
    app: FastAPI, *, lrt_namespace: LRTNamespace, containers_create: ContainersCreate
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.create_service_containers_task(
        rpc_client, lrt_namespace, containers_create
    )


@router.expose()
async def runs_docker_compose_down_task(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.runs_docker_compose_down_task(
        rpc_client, lrt_namespace
    )


@router.expose()
async def state_restore_task(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.state_restore_task(
        rpc_client, lrt_namespace
    )


@router.expose()
async def state_save_task(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.state_save_task(
        rpc_client, lrt_namespace
    )


@router.expose()
async def ports_inputs_pull_task(
    app: FastAPI,
    *,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.ports_inputs_pull_task(
        rpc_client, lrt_namespace, port_keys
    )


@router.expose()
async def ports_outputs_pull_task(
    app: FastAPI,
    *,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.ports_outputs_pull_task(
        rpc_client, lrt_namespace, port_keys
    )


@router.expose()
async def ports_outputs_push_task(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.ports_outputs_push_task(
        rpc_client, lrt_namespace
    )


@router.expose()
async def containers_restart_task(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.containers_restart_task(
        rpc_client, lrt_namespace
    )
