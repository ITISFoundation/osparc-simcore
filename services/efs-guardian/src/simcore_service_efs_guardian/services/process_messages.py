import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import DynamicServiceRunningMessage
from pydantic import parse_raw_as
from simcore_service_efs_guardian.services.modules.redis import get_redis_lock_client

from ..core.settings import get_application_settings
from ..services.efs_manager import EfsManager

_logger = logging.getLogger(__name__)


async def process_dynamic_service_running_message(app: FastAPI, data: bytes) -> bool:
    assert app  # nosec
    rabbit_message: DynamicServiceRunningMessage = parse_raw_as(
        DynamicServiceRunningMessage, data  # type: ignore[arg-type]
    )
    _logger.debug(
        "Process dynamic service running msg, project ID: %s node ID: %s",
        rabbit_message.project_id,
        rabbit_message.node_id,
    )

    settings = get_application_settings(app)
    efs_manager: EfsManager = app.state.efs_manager
    size = await efs_manager.get_project_node_data_size(
        rabbit_message.project_id, node_id=rabbit_message.node_id
    )

    if size > settings.EFS_DEFAULT_USER_SERVICE_SIZE_BYTES:
        _logger.warning(
            "Removing write permissions inside of EFS starts for project ID: %s, node ID: %s, current user: %s",
            rabbit_message.project_id,
            rabbit_message.node_id,
            rabbit_message.user_id,
        )
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
