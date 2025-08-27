from typing import cast

from models_library.api_schemas_directorv2.dynamic_services import ContainersCreate
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.errors import TaskAlreadyRunningError
from servicelib.long_running_tasks.models import LRTNamespace, TaskId
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ..modules import long_running_tasks


def _get_task_id_from_error(e: TaskAlreadyRunningError) -> str:
    return cast(str, e.managed_task.task_id)  # type: ignore[attr-defined] # pylint:disable=no-member


async def pull_container_images(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_pull_user_servcices_docker_images.__name__,
            unique=True,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def create_containers(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    containers_create: ContainersCreate,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_create_service_containers.__name__,
            unique=True,
            containers_create=containers_create,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def down_containers(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_runs_docker_compose_down.__name__,
            unique=True,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def restore_cotnainers_state(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_restore_state.__name__,
            unique=True,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def save_containers_state(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_save_state.__name__,
            unique=True,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def pull_container_port_inputs(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None = None,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_ports_inputs_pull.__name__,
            unique=True,
            port_keys=port_keys,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def pull_container_port_outputs(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_ports_outputs_pull.__name__,
            unique=True,
            port_keys=port_keys,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def push_container_port_outputs(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_ports_outputs_push.__name__,
            unique=True,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def restart_containers(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.task_containers_restart.__name__,
            unique=True,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)
