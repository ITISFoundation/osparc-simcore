from fastapi import FastAPI
from simcore_sdk.node_ports_common.r_clone_mount import RCloneMountManager

from ..core.settings import ApplicationSettings


def setup_r_clone_mount_manager(app: FastAPI):
    settings: ApplicationSettings = app.state.settings

    async def _on_startup() -> None:

        app.state.r_clone_mount_manager = r_clone_mount_manager = RCloneMountManager(
            settings.DY_SIDECAR_R_CLONE_SETTINGS
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
