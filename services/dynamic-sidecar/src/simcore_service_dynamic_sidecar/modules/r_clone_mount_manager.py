import logging
from functools import partial

from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStop,
)
from servicelib.logging_utils import log_context
from servicelib.rabbitmq.rpc_interfaces.dynamic_scheduler.services import (
    stop_dynamic_service,
)
from simcore_sdk.node_ports_common.r_clone_mount import RCloneMountManager

from ..core.rabbitmq import get_rabbitmq_rpc_client, post_sidecar_log_message
from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__file__)


async def _handle_shutdown_request(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings
    client = get_rabbitmq_rpc_client(app)

    with log_context(
        _logger, logging.INFO, "requesting service shutdown via dynamic-scheduler"
    ):
        await stop_dynamic_service(
            client,
            dynamic_service_stop=DynamicServiceStop(
                user_id=settings.DY_SIDECAR_USER_ID,
                project_id=settings.DY_SIDECAR_PROJECT_ID,
                node_id=settings.DY_SIDECAR_NODE_ID,
                simcore_user_agent="",
                save_state=True,
            ),
        )
        await post_sidecar_log_message(
            app,
            (
                "Your service was closed due to an issue that would create unexpected behavior. "
                "No data was lost. Thank you for your understanding."
            ),
            log_level=logging.WARNING,
        )


def setup_r_clone_mount_manager(app: FastAPI):
    settings: ApplicationSettings = app.state.settings

    async def _on_startup() -> None:

        app.state.r_clone_mount_manager = r_clone_mount_manager = RCloneMountManager(
            settings.DY_SIDECAR_R_CLONE_SETTINGS,
            handler_request_shutdown=partial(_handle_shutdown_request, app),
        )
        await r_clone_mount_manager.setup()

    async def _on_shutdown() -> None:
        r_clone_mount_manager: RCloneMountManager = app.state.r_clone_mount_manager
        await r_clone_mount_manager.teardown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


def get_r_clone_mount_manager(app: FastAPI) -> RCloneMountManager:
    assert isinstance(app.state.r_clone_mount_manager, RCloneMountManager)  # nosec
    return app.state.r_clone_mount_manager
