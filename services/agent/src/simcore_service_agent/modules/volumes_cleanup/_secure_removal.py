import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from servicelib.serial_executor import BaseSerialExecutor
from servicelib.sidecar_volumes import VolumeInfo, VolumeUtils

from ...core.settings import ApplicationSettings
from ._core import SidecarVolumes, backup_and_remove_sidecar_volumes

_logger = logging.getLogger(__name__)


class _VolumeRemovalExecutor(BaseSerialExecutor):
    async def run(  # pylint: disable=arguments-differ
        self, settings: ApplicationSettings, sidecar_volumes: SidecarVolumes
    ) -> None:
        await backup_and_remove_sidecar_volumes(
            settings=settings, sidecar_volumes=sidecar_volumes
        )


async def remove_sidecar_volumes(
    app: FastAPI,
    sidecar_volumes: SidecarVolumes,
    volume_remove_timeout_s: float | None = None,
) -> None:
    # NOTE: concurrent requests for removal of the same volume are queued.
    # Avoids concurrency issues between the background task and the director-v2 asking
    # for the volume removal.

    volume_removal_executor: _VolumeRemovalExecutor = app.state.volume_removal_executor
    settings: ApplicationSettings = app.state.settings

    volume_info: VolumeInfo = VolumeUtils.get_volume_info(
        sidecar_volumes.store_volume["Name"]
    )
    context_key = f"{volume_info.node_uuid}"

    if volume_remove_timeout_s is None:
        volume_remove_timeout_s = settings.AGENT_VOLUME_REMOVAL_TIMEOUT_S

    await volume_removal_executor.wait_for_result(
        settings=settings,
        sidecar_volumes=sidecar_volumes,
        timeout=volume_remove_timeout_s,
        context_key=context_key,
    )


def setup(app: FastAPI) -> None:
    async def _on_startup() -> None:
        with log_context(_logger, logging.INFO, "setup volume_removal_executor"):
            volume_removal_executor = (
                app.state.volume_removal_executor
            ) = _VolumeRemovalExecutor()

            await volume_removal_executor.start()

    async def _on_shutdown() -> None:
        with log_context(_logger, logging.INFO, "shutdown volume_removal_executor"):
            volume_removal_executor: _VolumeRemovalExecutor = (
                app.state.volume_removal_executor
            )
            await volume_removal_executor.stop()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
