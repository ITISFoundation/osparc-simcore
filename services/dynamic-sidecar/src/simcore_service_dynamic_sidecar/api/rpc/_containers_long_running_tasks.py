from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import ContainersCreate
from servicelib.long_running_tasks.models import LRTNamespace, TaskId
from servicelib.rabbitmq import RPCRouter

from ...core.rabbitmq import get_rabbitmq_rpc_client
from ...services import containers_long_running_tasks

router = RPCRouter()


@router.expose()
async def pull_container_images(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.pull_container_images(
        rpc_client, lrt_namespace
    )


@router.expose()
async def create_containers(
    app: FastAPI, *, lrt_namespace: LRTNamespace, containers_create: ContainersCreate
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.create_containers(
        rpc_client, lrt_namespace, containers_create
    )


@router.expose()
async def down_containers(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.down_containers(
        rpc_client, lrt_namespace
    )


@router.expose()
async def restore_cotnainers_state(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.restore_cotnainers_state(
        rpc_client, lrt_namespace
    )


@router.expose()
async def save_containers_state(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.save_containers_state(
        rpc_client, lrt_namespace
    )


@router.expose()
async def pull_container_port_inputs(
    app: FastAPI,
    *,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.pull_container_port_inputs(
        rpc_client, lrt_namespace, port_keys
    )


@router.expose()
async def pull_container_port_outputs(
    app: FastAPI,
    *,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.pull_container_port_outputs(
        rpc_client, lrt_namespace, port_keys
    )


@router.expose()
async def push_container_port_outputs(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.push_container_port_outputs(
        rpc_client, lrt_namespace
    )


@router.expose()
async def restart_containers(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.restart_containers(
        rpc_client, lrt_namespace
    )
