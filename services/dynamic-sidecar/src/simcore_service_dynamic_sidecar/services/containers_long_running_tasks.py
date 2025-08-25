from typing import cast

from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.errors import TaskAlreadyRunningError
from servicelib.long_running_tasks.models import LRTNamespace, TaskId
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ..core.settings import ApplicationSettings
from ..models.schemas.application_health import ApplicationHealth
from ..models.schemas.containers import ContainersCreate
from ..modules.inputs import InputsState
from ..modules.long_running_tasks import (
    task_containers_restart,
    task_create_service_containers,
    task_ports_inputs_pull,
    task_ports_outputs_pull,
    task_ports_outputs_push,
    task_pull_user_servcices_docker_images,
    task_restore_state,
    task_runs_docker_compose_down,
    task_save_state,
)


def _get_task_id_from_error(e: TaskAlreadyRunningError) -> str:
    return cast(str, e.managed_task.task_id)  # type: ignore[attr-defined] # pylint:disable=no-member


async def pull_user_services_docker_images(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_pull_user_servcices_docker_images.__name__,
            unique=True,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def create_service_containers_task(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    containers_create: ContainersCreate,
    settings: ApplicationSettings,
    application_health: ApplicationHealth,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_create_service_containers.__name__,
            unique=True,
            settings=settings,
            containers_create=containers_create,
            application_health=application_health,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def runs_docker_compose_down_task(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    settings: ApplicationSettings,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_runs_docker_compose_down.__name__,
            unique=True,
            settings=settings,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def state_restore_task(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    settings: ApplicationSettings,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_restore_state.__name__,
            unique=True,
            settings=settings,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def state_save_task(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    settings: ApplicationSettings,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_save_state.__name__,
            unique=True,
            settings=settings,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def ports_inputs_pull_task(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    settings: ApplicationSettings,
    inputs_state: InputsState,
    port_keys: list[str] | None = None,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_ports_inputs_pull.__name__,
            unique=True,
            port_keys=port_keys,
            settings=settings,
            inputs_pulling_enabled=inputs_state.inputs_pulling_enabled,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def ports_outputs_pull_task(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_ports_outputs_pull.__name__,
            unique=True,
            port_keys=port_keys,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def ports_outputs_push_task(
    rpc_client: RabbitMQRPCClient, lrt_namespace: LRTNamespace
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client, lrt_namespace, task_ports_outputs_push.__name__, unique=True
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)


async def containers_restart_task(
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    settings: ApplicationSettings,
) -> TaskId:
    try:
        return await lrt_api.start_task(
            rpc_client,
            lrt_namespace,
            task_containers_restart.__name__,
            unique=True,
            settings=settings,
        )
    except TaskAlreadyRunningError as e:
        return _get_task_id_from_error(e)
