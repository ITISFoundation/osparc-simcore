import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import DynamicServiceRunningMessage
from pydantic import ByteSize, parse_raw_as
from servicelib.logging_utils import log_context
from simcore_service_efs_guardian.services.modules.redis import get_redis_lock_client
from simcore_service_efs_guardian.services.notifier_setup import (
    EfsNodeDiskUsage,
    Notifier,
)

from ..core.settings import get_application_settings
from ..services.efs_manager import EfsManager

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
    efs_node_disk_usage = EfsNodeDiskUsage(
        node_id=rabbit_message.node_id,
        used=size,
        free=ByteSize(settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES - size),
        total=settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES,
        used_percent=round(size / settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES, 2),
    )
    notifier: Notifier = Notifier.get_from_app_state(app)
    await notifier.notify_service_efs_disk_usage(
        user_id=rabbit_message.user_id, efs_node_disk_usage=efs_node_disk_usage
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
