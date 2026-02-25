from typing import cast

from models_library.api_schemas_directorv2.dynamic_services import ContainersCreate
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.errors import TaskAlreadyRunningError
from servicelib.long_running_tasks.models import LRTNamespace, TaskId, TaskUniqueness
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ..modules import long_running_tasks


def _get_task_id_from_error(e: TaskAlreadyRunningError) -> str:
    return cast(str, e.managed_task.task_id)  # type: ignore[attr-defined] # pylint:disable=no-member


async def pull_user_services_images(rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.pull_user_services_images.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def create_user_services(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    containers_create: ContainersCreate,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.create_user_services.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
            containers_create=containers_create,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def remove_user_services(rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.remove_user_services.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def restore_user_services_state_paths(rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.restore_user_services_state_paths.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def save_user_services_state_paths(rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.save_user_services_state_paths.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def pull_user_services_input_ports(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None = None,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.pull_user_services_input_ports.__name__,
            uniqueness=TaskUniqueness.BY_NAME_AND_ARGS,
            port_keys=port_keys,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def pull_user_services_output_ports(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.pull_user_services_output_ports.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
            port_keys=port_keys,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def push_user_services_output_ports(rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.push_user_services_output_ports.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def restart_user_services(rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            long_running_tasks.restart_user_services.__name__,
            uniqueness=TaskUniqueness.BY_NAME,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)
