import asyncio
import logging
from asyncio import CancelledError, Future, Lock, Task
from asyncio import TimeoutError as AsyncioTimeoutError
from asyncio import create_task, wait_for
from contextlib import suppress
from functools import partial
from typing import Optional

from fastapi import FastAPI
from pydantic import PositiveFloat
from pydantic.errors import PydanticErrorMixin
from servicelib.logging_utils import log_context
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB

from ...core.rabbitmq import post_log_message
from ...core.settings import ApplicationSettings
from ..nodeports import upload_outputs
from ._context import OutputsContext

logger = logging.getLogger(__name__)


async def _cancel_task(task: Task, task_cancellation_timeout_s: PositiveFloat) -> None:
    task.cancel()
    with suppress(CancelledError):
        try:

            async def __await_task(task: Task) -> None:
                try:
                    await task
                except Exception:  # pylint:disable=broad-except
                    pass

            await wait_for(__await_task(task), timeout=task_cancellation_timeout_s)
        except AsyncioTimeoutError:
            logger.warning("Timed out while cancelling '%s'", task.get_name())


class UploadPortsFailed(PydanticErrorMixin, Exception):
    code: str = "dynamic_sidecar.outputs_manager.failed_while_uploading"
    msg_template: str = "Failed while uploading: failures={failures}"


class PortKeyTracker:
    def __init__(self) -> None:
        self._lock = Lock()

        self._pending_port_keys: set[str] = set()
        self._uploading_port_keys: set[str] = set()

    def __str__(self) -> str:
        return (
            f"pending={self._pending_port_keys} uploading={self._uploading_port_keys}"
        )

    async def add_pending(self, port_key: str) -> None:
        async with self._lock:
            self._pending_port_keys.add(port_key)

    async def are_pending_ports_uploading(self) -> bool:
        async with self._lock:
            return len(self._pending_port_keys & self._uploading_port_keys) > 0

    async def can_schedule_ports_to_upload(self) -> bool:
        async with self._lock:
            return (
                len(self._uploading_port_keys) == 0 and len(self._pending_port_keys) > 0
            )

    async def no_tracked_ports(self) -> bool:
        async with self._lock:
            return (
                len(self._pending_port_keys) == 0
                and len(self._uploading_port_keys) == 0
            )

    async def move_port_to_uploading(self) -> None:
        async with self._lock:
            port_key = self._pending_port_keys.pop()
            self._uploading_port_keys.add(port_key)

    async def move_all_ports_to_uploading(self) -> None:
        async with self._lock:
            self._uploading_port_keys.update(self._pending_port_keys)
            self._pending_port_keys.clear()

    async def get_uploading(self) -> list[str]:
        async with self._lock:
            return list(self._uploading_port_keys)

    async def move_all_uploading_to_pending(self) -> None:
        async with self._lock:
            self._pending_port_keys.update(self._uploading_port_keys)
            self._uploading_port_keys.clear()

    async def remove_all_uploading(self) -> None:
        async with self._lock:
            self._uploading_port_keys.clear()


class OutputsManager:  # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        outputs_context: OutputsContext,
        io_log_redirect_cb: Optional[LogRedirectCB],
        *,
        bulk_scheduling: bool = True,
        upload_upon_api_request: bool = True,
        task_cancellation_timeout_s: PositiveFloat = 5,
        task_monitor_interval_s: PositiveFloat = 1.0,
    ):
        self.outputs_context = outputs_context
        self.io_log_redirect_cb = io_log_redirect_cb
        self.bulk_scheduling = bulk_scheduling
        self.upload_upon_api_request = upload_upon_api_request
        self.task_cancellation_timeout_s = task_cancellation_timeout_s
        self.task_monitor_interval_s = task_monitor_interval_s

        self._port_key_tracker = PortKeyTracker()
        self._keep_running = True
        self._task_uploading: Optional[Task] = None
        self._task_scheduler_worker: Optional[Task] = None
        self._schedule_all_ports_for_upload: bool = False

        # keep track if a port was uploaded and there was an error, remove said error if
        self._last_upload_error_tracker: dict[str, Optional[Exception]] = {}

    async def _uploading_task_start(self) -> None:
        port_keys = await self._port_key_tracker.get_uploading()
        assert len(port_keys) > 0  # nosec

        task_name = f"outputs_manager_port_keys-{'_'.join(port_keys)}"
        self._task_uploading = create_task(
            upload_outputs(
                outputs_path=self.outputs_context.outputs_path,
                port_keys=port_keys,
                io_log_redirect_cb=self.io_log_redirect_cb,
            ),
            name=task_name,
        )

        def _remove_downloads(future: Future) -> None:
            # pylint: disable=protected-access
            if future._exception is not None:
                logger.warning(
                    "%s ended with exception: %s",
                    task_name,
                    future._exception
                    # traceback.format_tb(future._exception),
                )

            # keep track of the last result for each port
            for port_key in port_keys:
                try:
                    future.result()
                    self._last_upload_error_tracker[port_key] = None
                except Exception as e:  # pylint: disable=broad-except
                    self._last_upload_error_tracker[port_key] = e

            create_task(self._port_key_tracker.remove_all_uploading())

        self._task_uploading.add_done_callback(_remove_downloads)

    async def _uploading_task_cancel(self) -> None:
        if self._task_uploading is not None:
            await _cancel_task(self._task_uploading, self.task_cancellation_timeout_s)
            await self._port_key_tracker.move_all_uploading_to_pending()

    async def _scheduler_worker(self) -> None:
        while self._keep_running:
            if await self._port_key_tracker.are_pending_ports_uploading():
                await self._uploading_task_cancel()
                await self._port_key_tracker.move_all_uploading_to_pending()

            if await self._port_key_tracker.can_schedule_ports_to_upload():
                if self.bulk_scheduling:
                    await self._port_key_tracker.move_all_ports_to_uploading()
                else:
                    await self._port_key_tracker.move_port_to_uploading()

                await self._uploading_task_start()

            await asyncio.sleep(self.task_monitor_interval_s)

    def set_all_ports_for_upload(self) -> None:
        self._schedule_all_ports_for_upload = True

    async def start(self) -> None:
        self._task_scheduler_worker = create_task(
            self._scheduler_worker(), name="outputs_manager_scheduler_worker"
        )

    async def shutdown(self) -> None:
        with log_context(logger, logging.INFO, f"{OutputsManager.__name__} shutdown"):
            await self._uploading_task_cancel()
            if self._task_scheduler_worker is not None:
                await _cancel_task(
                    self._task_scheduler_worker, self.task_cancellation_timeout_s
                )

    async def port_key_content_changed(self, port_key: str) -> None:
        await self._port_key_tracker.add_pending(port_key)

    async def wait_for_all_uploads_to_finish(self) -> None:
        """
        if there are no pending port uploads return immediately
        otherwise wait for all of them to finish
        """
        # NOTE: the file system watchdog was found unhealthy and to make
        # sure we are not uploading a partially updated state we mark all
        # ports changed.
        # This will cancel and reupload all the data, ensuring no data
        # is missed.
        if self._schedule_all_ports_for_upload:
            self._schedule_all_ports_for_upload = False
            logger.warning(
                "Scheduled %s for upload. The watchdog was rebooted. "
                "This is a safety measure to make sure no data is lost. ",
                self.outputs_context.outputs_path,
            )
            for port_key in self.outputs_context.port_keys:
                await self.port_key_content_changed(port_key)

        while not await self._port_key_tracker.no_tracked_ports():
            await asyncio.sleep(self.task_monitor_interval_s)

        # NOTE: checking if there were any errors during the last port upload,
        # for each port. If such errors are present an error will be raised
        any_failed_upload = any(
            True for v in self._last_upload_error_tracker.values() if v is not None
        )
        if any_failed_upload:
            raise UploadPortsFailed(failures=self._last_upload_error_tracker)


def setup_outputs_manager(app: FastAPI) -> None:
    async def on_startup() -> None:
        assert isinstance(app.state.outputs_context, OutputsContext)  # nosec
        outputs_context: OutputsContext = app.state.outputs_context
        assert isinstance(app.state.settings, ApplicationSettings)  # nosec
        settings: ApplicationSettings = app.state.settings

        io_log_redirect_cb: Optional[LogRedirectCB] = None
        if settings.RABBIT_SETTINGS:
            io_log_redirect_cb = partial(post_log_message, app)
        logger.debug(
            "setting up outputs manager %s",
            "with redirection of logs..." if io_log_redirect_cb else "...",
        )

        outputs_manager = app.state.outputs_manager = OutputsManager(
            outputs_context=outputs_context,
            io_log_redirect_cb=io_log_redirect_cb,
        )
        await outputs_manager.start()

    async def on_shutdown() -> None:
        outputs_manager: Optional[OutputsManager] = app.state.outputs_manager
        if outputs_manager is not None:
            await outputs_manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
