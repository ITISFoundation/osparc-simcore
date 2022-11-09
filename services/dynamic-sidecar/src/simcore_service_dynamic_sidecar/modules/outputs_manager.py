import asyncio
import logging
from asyncio import CancelledError, Future, Task
from asyncio import TimeoutError as AsyncioTimeoutError
from asyncio import create_task, wait_for
from contextlib import suppress
from dataclasses import dataclass
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


@dataclass
class _TrackedTask:
    port_key: str
    task: Task


class OutputsManager:
    def __init__(
        self,
        outputs_path: Path,
        nodeports: Nodeports,
        *,
        upload_upon_api_request: bool = True,
        cancellation_timeout: PositiveFloat = 10,
        task_monitor_interval_s: PositiveFloat = 1.0,
    ):
        self.outputs_path = outputs_path
        self.nodeports = nodeports
        self.upload_upon_api_request = upload_upon_api_request
        self.cancellation_timeout = cancellation_timeout
        self.task_monitor_interval_s = task_monitor_interval_s

        self.outputs_port_keys: set[str] = set()

        self._scheduled_port_key_uploads: set[str] = set()
        self._current_upload: Optional[_TrackedTask] = None
        self._tracked_upload_awaiter_tasks: dict[str, Task] = {}

    def _check_port_key(self, port_key: str) -> None:
        if port_key not in self.outputs_port_keys:
            raise RuntimeError(
                f"Provided {port_key=} was not detected in {self.outputs_port_keys=}"
            )

    async def _cancel_upload_task(self) -> None:
        """stops unique upload task currently running"""
        if self._current_upload is None:
            return

        self._current_upload.task.cancel()
        with suppress(CancelledError):
            try:

                async def __await_task(task: Task) -> None:
                    await task

                await wait_for(
                    __await_task(self._current_upload.task),
                    timeout=self.cancellation_timeout,
                )
            except AsyncioTimeoutError:
                logger.warning(
                    "Timed out while cancelling port_key '%s' upload",
                    self._current_upload.port_key,
                )
        self._current_upload = None

    def _schedule_port_upload(self) -> None:
        """start a new upload task if requests are available"""
        logger.debug(
            "RUNNING SCHEDULER: %s %s",
            self._scheduled_port_key_uploads,
            self._current_upload,
        )
        if len(self._scheduled_port_key_uploads) == 0:
            logger.debug("No more scheduled port_key uploads")
            return

        if self._current_upload is not None:
            logger.debug(
                "Currently handling %s, will not schedule a new upload",
                self._current_upload.port_key,
            )
            return

        a_port_key = self._scheduled_port_key_uploads.pop()
        logger.debug("Scheduling '%s'", a_port_key)

        def _remove_and_try_to_reschedule(_: Future) -> None:
            self._current_upload = None
            self._schedule_port_upload()

        task = create_task(
            upload_outputs(
                outputs_path=self.outputs_path,
                port_keys=[a_port_key],
                nodeports=self.nodeports,
            ),
            name=f"upload_port_key_{a_port_key}",
        )
        task.add_done_callback(_remove_and_try_to_reschedule)
        self._current_upload = _TrackedTask(port_key=a_port_key, task=task)

    async def _wait_port_to_upload(self, port_key: str) -> Task:
        """
        reruns a Task which waits for the upload to finish (can be optionally awaited)
        """

        async def _task_optionally_awaitable() -> None:
            def _is_port_waiting_or_uploading() -> bool:
                port_is_waiting_to_upload = port_key in self._scheduled_port_key_uploads
                port_task_is_uploading = (
                    self._current_upload is not None
                    and port_key == self._current_upload.port_key
                )
                return port_is_waiting_to_upload or port_task_is_uploading

            while _is_port_waiting_or_uploading():
                current_port_key_task = (
                    None
                    if self._current_upload is None
                    else self._current_upload.port_key
                )
                logger.debug(
                    "Waiting for '%s' to finish or start, currently handling '%s'",
                    port_key,
                    current_port_key_task,
                )
                await asyncio.sleep(self.task_monitor_interval_s)

            logger.info("Finished upload for '%s'", port_key)

        task = asyncio.create_task(
            _task_optionally_awaitable(), name=f"waiting_for_port_to_upload_{port_key}"
        )
        task.add_done_callback(
            partial(
                lambda p, _: self._tracked_upload_awaiter_tasks.pop(p, None),
                port_key,
            )
        )
        self._tracked_upload_awaiter_tasks[port_key] = task
        return task

    async def _request_port_upload(
        self, port_content_changed: bool, port_key: str
    ) -> Task:
        """
        Decides to cancel, keep or schedule a new upload task.
        returns a Task which waits for the upload to finish (can be optionally awaited)
        """
        # | # | same_port_as_upload | port_content_changed | upload_exists | action            |
        # |---|---------------------|----------------------|---------------|-------------------|
        # | 1 | false               | false                | false         | schedule          |
        # | 2 | false               | false                | true          | schedule          |
        # | 3 | false               | true                 | false         | schedule          |
        # | 4 | false               | true                 | true          | schedule          |
        # | 5 | true                | false                | false         | schedule          |
        # | 6 | true                | false                | true          | N/A               |
        # | 7 | true                | true                 | false         | schedule          |
        # | 8 | true                | true                 | true          | cancel & schedule |

        upload_exists = self._current_upload is not None
        same_port_as_upload = (
            self._current_upload is not None
            and port_key == self._current_upload.port_key
        )

        # 6: return tas already running just wait for it to finish
        if same_port_as_upload and not port_content_changed and upload_exists:
            return await self._wait_port_to_upload(port_key)

        # 8: cancel current task
        if same_port_as_upload and port_content_changed and upload_exists:
            await self._cancel_upload_task()

        self._scheduled_port_key_uploads.add(port_key)
        self._schedule_port_upload()

        return await self._wait_port_to_upload(port_key)

    async def shutdown(self) -> None:
        await self._cancel_upload_task()
        # can change length during iteration
        for port_key in set(self._tracked_upload_awaiter_tasks.keys()):
            task = self._tracked_upload_awaiter_tasks.pop(port_key, None)
            if task is None:
                continue

            task.cancel()

            with suppress(asyncio.CancelledError):
                await task

        logger.info("outputs manger shut down")

    async def upload_after_port_change(self, port_key: str) -> None:
        """
        Request to upload after a change in the port's directory
        was observed.

        Used by the DirectoryWatcher.
        """
        self._check_port_key(port_key)
        await self._request_port_upload(port_content_changed=True, port_key=port_key)

    async def upload_port(self, port_key: str) -> None:
        """
        Request a port upload, and waits for the upload to finish.

        Used by the API endpoint.
        """
        self._check_port_key(port_key)
        task = await self._request_port_upload(
            port_content_changed=False, port_key=port_key
        )
        await task


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

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
