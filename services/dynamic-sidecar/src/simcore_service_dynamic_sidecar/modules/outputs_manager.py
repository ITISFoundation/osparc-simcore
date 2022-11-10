import asyncio
import logging
import random
from asyncio import CancelledError, Future, Queue, Task
from asyncio import TimeoutError as AsyncioTimeoutError
from asyncio import create_task, wait_for
from contextlib import suppress
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

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


def _get_upload_task(port_key: str, outputs_path: Path, nodeports: Nodeports) -> Task:
    return create_task(
        upload_outputs(
            outputs_path=outputs_path, port_keys=[port_key], nodeports=nodeports
        ),
        name=f"upload_task__{port_key}",
    )


async def _cancel_task(task: Task, cancellation_timeout_s: PositiveFloat) -> None:
    task.cancel()
    with suppress(CancelledError):
        try:

            async def __await_task(task: Task) -> None:
                await task

            await wait_for(__await_task(task), timeout=cancellation_timeout_s)
        except AsyncioTimeoutError:
            logger.warning("Timed out while cancelling '%s'", task.get_name())


@dataclass
class _PortUploadManager:
    port_key: str
    _observer_queue: list[Queue[Optional[Future]]] = field(default_factory=list)
    _cancel_and_reschedule: bool = False
    _cancel_task: bool = False

    def cancel_and_reschedule(self) -> None:
        self._cancel_and_reschedule = True

    def cancel(self) -> None:
        self._cancel_task = True

    async def run_upload_task(
        self,
        outputs_path: Path,
        nodeports: Nodeports,
        cancellation_timeout_s: PositiveFloat,
        task_polling_interval_s: PositiveFloat = 0.1,
    ) -> None:
        upload_task = _get_upload_task(self.port_key, outputs_path, nodeports)

        # wait for task to finish
        while not upload_task.done():
            if self._cancel_and_reschedule:
                self._cancel_and_reschedule = False

                # cancel current task and recreate upload_task
                await _cancel_task(upload_task, cancellation_timeout_s)
                upload_task = _get_upload_task(self.port_key, outputs_path, nodeports)

            if self._cancel_task:
                # cancel current upload return the result as canceled
                upload_task.cancel()
                break

            await asyncio.sleep(task_polling_interval_s)

        # send results to observers
        for queue in self._observer_queue:
            queue.put_nowait(upload_task)

        # wait for observers to pick up result
        await asyncio.gather(*[queue.get() for queue in self._observer_queue])

    async def wait_for_result(self) -> Future:
        """Blocks and waits for the task to finish and provide a result"""
        result_queue: Queue[Optional[Future]] = Queue()
        self._observer_queue.append(result_queue)

        # wait for a result to become available
        future = await result_queue.get()
        await result_queue.put(None)  # done with this

        assert isinstance(future, Future)  # nosec
        return future


class OutputsManager:  # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        outputs_path: Path,
        nodeports: Nodeports,
        *,
        upload_upon_api_request: bool = True,
        cancellation_timeout_s: PositiveFloat = 10,
        task_monitor_interval_s: PositiveFloat = 1.0,
    ):
        self.outputs_path = outputs_path
        self.nodeports = nodeports
        self.upload_upon_api_request = upload_upon_api_request
        self.cancellation_timeout_s = cancellation_timeout_s
        self.task_monitor_interval_s = task_monitor_interval_s

        self.outputs_port_keys: set[str] = set()

        # new scheduler
        self._pending_port_uploads: dict[str, _PortUploadManager] = {}
        self._current_port_upload: Optional[_PortUploadManager] = None
        self._upload_worker_task: Optional[Task] = None
        self._tracked_port_upload_tasks: dict[str, Task] = {}

    def _check_port_key(self, port_key: str) -> None:
        if port_key not in self.outputs_port_keys:
            raise RuntimeError(
                f"Provided {port_key=} was not detected in {self.outputs_port_keys=}"
            )

    async def _wait_for_upload_task(self, port_key: str) -> Future:
        upload_task = self._pending_port_uploads[port_key]
        return await upload_task.wait_for_result()

    async def _schedule_upload_task(self, port_key: str) -> None:
        port_pending_upload = port_key in self._pending_port_uploads
        port_is_currently_uploading = (
            self._current_port_upload is not None
            and self._current_port_upload.port_key == port_key
        )
        if not port_pending_upload and not port_is_currently_uploading:
            self._pending_port_uploads[port_key] = _PortUploadManager(port_key=port_key)

    async def _upload_worker(self) -> None:
        while True:
            if self._current_port_upload is not None:
                await self._current_port_upload.run_upload_task(
                    self.outputs_path, self.nodeports, self.cancellation_timeout_s
                )
                self._current_port_upload = None

            elif len(self._pending_port_uploads) > 0:
                # reschedule next if available
                random_key = random.choice(tuple(self._pending_port_uploads.keys()))
                self._current_port_upload = self._pending_port_uploads.pop(
                    random_key, None
                )

            await asyncio.sleep(self.task_monitor_interval_s)

    async def _request_port_upload(
        self, port_content_changed: bool, port_key: str
    ) -> Future:
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

        upload_exists = self._current_port_upload is not None
        same_port_as_upload = (
            self._current_port_upload is not None
            and port_key == self._current_port_upload.port_key
        )

        # 6: return tas already running just wait for it to finish
        if same_port_as_upload and not port_content_changed and upload_exists:
            return await self._wait_for_upload_task(port_key)

        # 8: cancel current task
        if same_port_as_upload and port_content_changed and upload_exists:
            assert isinstance(self._current_port_upload, _PortUploadManager)  # nosec
            self._current_port_upload.cancel_and_reschedule()
            return await self._wait_for_upload_task(port_key)

        await self._schedule_upload_task(port_key)
        return await self._wait_for_upload_task(port_key)

    async def upload_after_port_change(self, port_key: str) -> None:
        """
        Request to upload after a change in the port's directory
        was observed.

        Used by the DirectoryWatcher.
        """
        self._check_port_key(port_key)

        task_name = f"port_upload_{port_key}_{uuid4()}"
        upload_task = create_task(
            self._request_port_upload(port_content_changed=True, port_key=port_key),
            name=task_name,
        )
        upload_task.add_done_callback(
            partial(
                lambda s, _: self._tracked_port_upload_tasks.pop(s, None),
                task_name,
            )
        )
        self._tracked_port_upload_tasks[task_name] = upload_task

    async def upload_port(self, port_key: str) -> Any:
        """
        Request a port upload, and waits for the upload to finish.

        Used by the API endpoint.
        """
        self._check_port_key(port_key)
        future = await self._request_port_upload(
            port_content_changed=False, port_key=port_key
        )
        # NOTE: below will raise an error or return a result
        # allows for error propagation from nodeports
        return future.result()

    async def start(self) -> None:
        self._upload_worker_task = create_task(
            self._upload_worker(), name="upload_worker_task"
        )
        logger.info("outputs manger started")

    async def shutdown(self) -> None:
        if self._current_port_upload is not None:
            self._current_port_upload.cancel()

        if self._upload_worker_task is not None:
            await _cancel_task(self._upload_worker_task, self.cancellation_timeout_s)

        for key in set(self._tracked_port_upload_tasks.keys()):
            task = self._tracked_port_upload_tasks.pop(key, None)
            if task is not None:
                await _cancel_task(task, self.cancellation_timeout_s)

        logger.info("outputs manger shut down")


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

        outputs_manager = app.state.outputs_manager = OutputsManager(
            outputs_path=mounted_volumes.disk_outputs_path, nodeports=nodeports
        )
        await outputs_manager.start()

    async def on_shutdown() -> None:
        outputs_manager: Optional[OutputsManager] = app.state.outputs_manager
        if outputs_manager is not None:
            await outputs_manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
