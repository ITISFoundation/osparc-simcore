from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import ContainersCreate
from servicelib.long_running_tasks.models import LRTNamespace, TaskId
from servicelib.rabbitmq import RPCRouter

from ...core.rabbitmq import get_rabbitmq_rpc_client
from ...services import containers_long_running_tasks

router = RPCRouter()


@router.expose()
async def pull_user_services_images(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.pull_user_services_images(
        rpc_client, lrt_namespace
    )


@router.expose()
async def create_user_services(
    app: FastAPI, *, lrt_namespace: LRTNamespace, containers_create: ContainersCreate
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.create_user_services(
        rpc_client, lrt_namespace, containers_create
    )


@router.expose()
async def remove_user_services(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.remove_user_services(
        rpc_client, lrt_namespace
    )


@router.expose()
async def restore_user_services_state_paths(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.restore_user_services_state_paths(
        rpc_client, lrt_namespace
    )


@router.expose()
async def save_user_services_state_paths(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.save_user_services_state_paths(
        rpc_client, lrt_namespace
    )


@router.expose()
async def pull_user_services_input_ports(
    app: FastAPI,
    *,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.pull_user_services_input_ports(
        rpc_client, lrt_namespace, port_keys
    )


@router.expose()
async def pull_user_services_output_ports(
    app: FastAPI,
    *,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.pull_user_services_output_ports(
        rpc_client, lrt_namespace, port_keys
    )


@router.expose()
async def push_user_services_output_ports(
    app: FastAPI, *, lrt_namespace: LRTNamespace
) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.push_user_services_output_ports(
        rpc_client, lrt_namespace
    )


@router.expose()
async def restart_user_services(app: FastAPI, *, lrt_namespace: LRTNamespace) -> TaskId:
    rpc_client = get_rabbitmq_rpc_client(app)
    return await containers_long_running_tasks.restart_user_services(
        rpc_client, lrt_namespace
    )
