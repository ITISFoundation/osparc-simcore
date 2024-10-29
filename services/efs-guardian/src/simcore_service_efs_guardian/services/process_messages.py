import logging

from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from models_library.rabbitmq_messages import DynamicServiceRunningMessage
from pydantic import parse_raw_as
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar.disk_usage import (
    update_disk_usage,
)
from servicelib.utils import fire_and_forget_task

from ..core.settings import get_application_settings
from ..services.efs_manager import EfsManager
from ..services.modules.rabbitmq import get_rabbitmq_rpc_client
from ..services.modules.redis import get_redis_lock_client

_logger = logging.getLogger(__name__)


async def process_dynamic_service_running_message(app: FastAPI, data: bytes) -> bool:
    assert app  # nosec
    rabbit_message: DynamicServiceRunningMessage = parse_raw_as(
        DynamicServiceRunningMessage, data
    )
    _logger.debug(
        "Process dynamic service running msg, project ID: %s node ID: %s, current user: %s",
        rabbit_message.project_id,
        rabbit_message.node_id,
        rabbit_message.user_id,
    )

    settings = get_application_settings(app)
    efs_manager: EfsManager = app.state.efs_manager

    dir_exists = await efs_manager.check_project_node_data_directory_exits(
        rabbit_message.project_id, node_id=rabbit_message.node_id
    )
    if dir_exists is False:
        _logger.debug(
            "Directory doesn't exists in EFS, project ID: %s node ID: %s, current user: %s",
            rabbit_message.project_id,
            rabbit_message.node_id,
            rabbit_message.user_id,
        )
        return True

    size = await efs_manager.get_project_node_data_size(
        rabbit_message.project_id, node_id=rabbit_message.node_id
    )
    _logger.debug(
        "Current directory size: %s, project ID: %s node ID: %s, current user: %s",
        size,
        rabbit_message.project_id,
        rabbit_message.node_id,
        rabbit_message.user_id,
    )

    project_node_state_names = await efs_manager.list_project_node_state_names(
        rabbit_message.project_id, node_id=rabbit_message.node_id
    )
    rpc_client: RabbitMQRPCClient = get_rabbitmq_rpc_client(app)
    _used = min(size, settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES)
    usage: dict[str, DiskUsage] = {}
    for name in project_node_state_names:
        usage[name] = DiskUsage.from_efs_guardian(
            used=_used, total=settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES
        )

    fire_and_forget_task(
        update_disk_usage(rpc_client, node_id=rabbit_message.node_id, usage=usage),
        task_suffix_name=f"update_disk_usage_efs_user_id{rabbit_message.user_id}_node_id{rabbit_message.node_id}",
        fire_and_forget_tasks_collection=app.state.efs_guardian_fire_and_forget_tasks,
    )

    if size > settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES:
        msg = f"Removing write permissions inside of EFS starts for project ID: {rabbit_message.project_id}, node ID: {rabbit_message.node_id}, current user: {rabbit_message.user_id}, size: {size}, upper limit: {settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES}"
        with log_context(_logger, logging.WARNING, msg=msg):
            redis = get_redis_lock_client(app)
            async with redis.lock_context(
                f"efs_remove_write_permissions-{rabbit_message.project_id=}-{rabbit_message.node_id=}",
                blocking=True,
                blocking_timeout_s=10,
            ):
                await efs_manager.remove_project_node_data_write_permissions(
                    project_id=rabbit_message.project_id, node_id=rabbit_message.node_id
                )

    return True
