import logging
from asyncio import CancelledError, Lock, Task
from asyncio import TimeoutError as AsyncioTimeoutError
from asyncio import create_task, wait_for
from contextlib import suppress
from functools import partial
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from pydantic import PositiveFloat
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from simcore_sdk.node_ports_v2 import Nodeports
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings

from ..core.rabbitmq import send_message
from .mounted_fs import MountedVolumes
from .nodeports import upload_outputs

logger = logging.getLogger(__name__)


class OutputsManager:
    def __init__(
        self,
        outputs_path: Path,
        nodeports: Nodeports,
        *,
        upload_upon_api_request: bool = True,
        cancellation_timeout: PositiveFloat = 20,
    ):
        self.outputs_path = outputs_path
        self.nodeports = nodeports
        self.upload_upon_api_request = upload_upon_api_request
        self.cancellation_timeout = cancellation_timeout

        self._lock = Lock()
        self.outputs_port_keys: set[str] = set()
        self._current_uploads: dict[str, Task] = {}

    def _check_port_key(self, port_key: str) -> None:
        if port_key not in self.outputs_port_keys:
            raise RuntimeError(
                f"Provided {port_key=} was not detected in {self.outputs_port_keys=}"
            )

    def _nodeports_upload_port(self, port_key: str) -> Task:
        task = self._current_uploads[port_key] = create_task(
            upload_outputs(
                outputs_path=self.outputs_path,
                port_keys=[port_key],
                nodeports=self.nodeports,
            ),
            name=f"upload_port_key_{port_key}",
        )
        # remove task when completed
        task.add_done_callback(
            partial(lambda s, _: self._current_uploads.pop(s, None), port_key)
        )
        return task

    async def _cancel_task(self, port_key: str) -> None:
        task = self._current_uploads.get(port_key, None)
        if task is None:
            return

        task.cancel()
        with suppress(CancelledError):
            try:

                async def __await_task(task: Task) -> None:
                    await task

                await wait_for(__await_task(task), timeout=self.cancellation_timeout)
            except AsyncioTimeoutError:
                logger.warning(
                    "Timed out while cancelling port_key '%s' upload", port_key
                )

    async def _trigger_port_upload(
        self,
        content_changed: bool,
        port_key: str,
    ) -> Optional[Task]:
        """
        If an upload is already ongoing decides if it must
        keep it or cancel it and retry.
        """
        # NOTE: one lock for all the ports is sufficient
        async with self._lock:

            # content changed and upload is already in progress
            # cancel it and reschedule
            upload_ongoing = port_key in self._current_uploads

            # an upload is already ongoing
            if upload_ongoing and not content_changed:
                return None

            # if content is out of data cancel upload and retry
            if upload_ongoing and content_changed:
                await self._cancel_task(port_key)

                return self._nodeports_upload_port(port_key)

            # always upload if content changed
            if content_changed:
                return self._nodeports_upload_port(port_key)

            # is it always requested to upload
            if self.upload_upon_api_request:
                return self._nodeports_upload_port(port_key)
        return None

    async def shutdown(self) -> None:
        # dictionary can change during iteration
        for port_key in set(self._current_uploads.keys()):
            await self._cancel_task(port_key)

    async def upload_after_port_change(self, port_key: str) -> None:
        """
        Request to upload after a change in the port's directory
        was observed.

        Used by the DirectoryWatcher.
        """
        self._check_port_key(port_key)
        await self._trigger_port_upload(content_changed=True, port_key=port_key)

    async def upload_port(self, port_key: str) -> Optional[Task]:
        """
        Request a port upload.
        returns: a task relative to  an upload if one is required.
        Returned task can be optionally awaited.

        Used by the API endpoint.
        """
        self._check_port_key(port_key)

        return await self._trigger_port_upload(content_changed=False, port_key=port_key)


def setup_outputs_manager(app: FastAPI) -> None:
    async def on_startup() -> None:
        assert isinstance(app.state.mounted_volumes, MountedVolumes)  # nosec
        mounted_volumes: MountedVolumes = app.state.mounted_volumes
        assert isinstance(app.state.settings, ApplicationSettings)  # nosec
        settings: ApplicationSettings = app.state.settings

        io_log_redirect_cb: Optional[LogRedirectCB] = None
        if settings.RABBIT_SETTINGS:
            io_log_redirect_cb = partial(send_message, app.state.rabbitmq)
        logger.debug(
            "setting up outputs manager %s",
            "with redirection of logs..." if io_log_redirect_cb else "...",
        )

        nodeports: Nodeports = await node_ports_v2.ports(
            user_id=settings.DY_SIDECAR_USER_ID,
            project_id=ProjectIDStr(settings.DY_SIDECAR_PROJECT_ID),
            node_uuid=NodeIDStr(settings.DY_SIDECAR_NODE_ID),
            r_clone_settings=settings.rclone_settings_for_nodeports,
            io_log_redirect_cb=io_log_redirect_cb,
        )

        app.state.outputs_manager = OutputsManager(
            outputs_path=mounted_volumes.disk_outputs_path, nodeports=nodeports
        )

        logger.info("outputs manger started")

    async def on_shutdown() -> None:
        outputs_manager: Optional[OutputsManager] = app.state.outputs_manager
        if outputs_manager is not None:
            await outputs_manager.shutdown()

            logger.info("outputs manger shut down")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
