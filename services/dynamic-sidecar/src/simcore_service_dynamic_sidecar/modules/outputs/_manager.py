import asyncio
import logging
import traceback
from asyncio import CancelledError, Future, Lock, Task, create_task, wait
from contextlib import suppress
from datetime import timedelta
from functools import partial

from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from models_library.basic_types import IDStr
from models_library.rabbitmq_messages import ProgressType
from pydantic import PositiveFloat
from servicelib import progress_bar
from servicelib.background_task import start_periodic_task, stop_periodic_task
from servicelib.logging_utils import log_catch, log_context
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB

from ...core.rabbitmq import post_log_message, post_progress_message
from ...core.settings import ApplicationSettings
from ...modules.notifications._notifications_ports import PortNotifier
from ..nodeports import upload_outputs
from ._context import OutputsContext

_logger = logging.getLogger(__name__)


async def _cancel_task(task: Task, task_cancellation_timeout_s: PositiveFloat) -> None:
    task.cancel()
    with suppress(CancelledError), log_catch(_logger, reraise=False):
        await wait((task,), timeout=task_cancellation_timeout_s)


class UploadPortsFailedError(OsparcErrorMixin, RuntimeError):
    code: str = "dynamic_sidecar.outputs_manager.failed_while_uploading"  # type: ignore[assignment]
    msg_template: str = "Failed while uploading: failures={failures}"


class _PortKeyTracker:
    """
    Once a port requires upload is added here to be tracked.
    While a port is tracked it can be in two states:
    - `pending` port waiting to be uploaded
    - `uploading` port upload in progress

    """

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
        port_notifier: PortNotifier,
        io_log_redirect_cb: LogRedirectCB | None,
        progress_cb: progress_bar.AsyncReportCB | None,
        *,
        upload_upon_api_request: bool = True,
        task_cancellation_timeout_s: PositiveFloat = 5,
        task_monitor_interval_s: PositiveFloat = 1.0,
    ):
        self.outputs_context = outputs_context
        self.port_notifier = port_notifier
        self.io_log_redirect_cb = io_log_redirect_cb
        self.upload_upon_api_request = upload_upon_api_request
        self.task_cancellation_timeout_s = task_cancellation_timeout_s
        self.task_monitor_interval_s = task_monitor_interval_s
        self.task_progress_cb = progress_cb

        self._port_key_tracker = _PortKeyTracker()
        self._task_uploading: Task | None = None
        self._task_scheduler_worker: Task | None = None
        self._schedule_all_ports_for_upload: bool = False

        # keep track if a port was uploaded and there was an error, remove said error if
        self._last_upload_error_tracker: dict[str, Exception | None] = {}

    async def _uploading_task_start(self) -> None:
        port_keys = await self._port_key_tracker.get_uploading()
        assert len(port_keys) > 0  # nosec

        async def _upload_ports() -> None:
            with log_context(
                _logger, logging.INFO, f"Uploading port keys: {port_keys}"
            ):
                async with progress_bar.ProgressBarData(
                    num_steps=1,
                    progress_report_cb=self.task_progress_cb,
                    description=IDStr("uploading ports"),
                ) as root_progress:
                    await upload_outputs(
                        outputs_path=self.outputs_context.outputs_path,
                        port_keys=port_keys,
                        io_log_redirect_cb=self.io_log_redirect_cb,
                        progress_bar=root_progress,
                        port_notifier=self.port_notifier,
                    )

        task_name = f"outputs_manager_port_keys-{'_'.join(port_keys)}"
        self._task_uploading = create_task(_upload_ports(), name=task_name)

        def _remove_downloads(future: Future) -> None:
            # pylint: disable=protected-access
            if future._exception is not None:
                formatted_traceback = (
                    "\n" + "".join(traceback.format_exception(future._exception))
                    if future._exception.__traceback__
                    else ""
                )
                _logger.warning(
                    "%s ended with exception: %s%s",
                    task_name,
                    future._exception,
                    formatted_traceback,
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
        if await self._port_key_tracker.are_pending_ports_uploading():
            await self._uploading_task_cancel()
            await self._port_key_tracker.move_all_uploading_to_pending()

        if await self._port_key_tracker.can_schedule_ports_to_upload():
            await self._port_key_tracker.move_all_ports_to_uploading()

            await self._uploading_task_start()

    def set_all_ports_for_upload(self) -> None:
        self._schedule_all_ports_for_upload = True

    async def start(self) -> None:
        self._task_scheduler_worker = start_periodic_task(
            self._scheduler_worker,
            interval=timedelta(seconds=self.task_monitor_interval_s),
            task_name="outputs_manager_scheduler_worker",
        )

    async def shutdown(self) -> None:
        with log_context(_logger, logging.INFO, f"{OutputsManager.__name__} shutdown"):
            await self._uploading_task_cancel()
            if self._task_scheduler_worker is not None:
                await stop_periodic_task(
                    self._task_scheduler_worker, timeout=self.task_monitor_interval_s
                )

    async def port_key_content_changed(self, port_key: str) -> None:
        await self._port_key_tracker.add_pending(port_key)

    async def wait_for_all_uploads_to_finish(self) -> None:
        """
        Waits for all ports to finish uploads. If there are also
        non file based output ports, schedule them for upload at this time.

        If there are no pending port uploads return immediately
        otherwise wait for all of them to finish
        """

        # always scheduling non file based ports for upload
        # there is no auto detection when these change
        for non_file_port_key in self.outputs_context.non_file_type_port_keys:
            _logger.info("Adding non file port key %s", non_file_port_key)
            await self.port_key_content_changed(non_file_port_key)

        # NOTE: the file system watchdog was found unhealthy and to make
        # sure we are not uploading a partially updated state we mark all
        # ports changed.
        # This will cancel and reupload all the data, ensuring no data
        # is missed.
        if self._schedule_all_ports_for_upload:
            self._schedule_all_ports_for_upload = False
            _logger.warning(
                "Scheduled %s for upload. The watchdog was rebooted. "
                "This is a safety measure to make sure no data is lost. ",
                self.outputs_context.outputs_path,
            )
            for file_port_key in self.outputs_context.file_type_port_keys:
                await self.port_key_content_changed(file_port_key)

        _logger.info("Port status before waiting %s", f"{self._port_key_tracker}")
        while not await self._port_key_tracker.no_tracked_ports():
            await asyncio.sleep(self.task_monitor_interval_s)
        _logger.info("Port status after waiting %s", f"{self._port_key_tracker}")

        # NOTE: checking if there were any errors during the last port upload,
        # for each port. If any error is detected this will raise.
        any_failed_upload = any(
            True for v in self._last_upload_error_tracker.values() if v is not None
        )
        if any_failed_upload:
            raise UploadPortsFailedError(failures=self._last_upload_error_tracker)


def setup_outputs_manager(app: FastAPI) -> None:
    async def on_startup() -> None:
        assert isinstance(app.state.outputs_context, OutputsContext)  # nosec
        outputs_context: OutputsContext = app.state.outputs_context
        assert isinstance(app.state.settings, ApplicationSettings)  # nosec
        settings: ApplicationSettings = app.state.settings

        io_log_redirect_cb: LogRedirectCB | None = None
        if settings.RABBIT_SETTINGS:
            io_log_redirect_cb = partial(post_log_message, app, log_level=logging.INFO)
        _logger.debug(
            "setting up outputs manager %s",
            "with redirection of logs..." if io_log_redirect_cb else "...",
        )

        outputs_manager = app.state.outputs_manager = OutputsManager(
            outputs_context=outputs_context,
            io_log_redirect_cb=io_log_redirect_cb,
            progress_cb=partial(
                post_progress_message, app, ProgressType.SERVICE_OUTPUTS_PUSHING
            ),
            port_notifier=PortNotifier(
                app,
                settings.DY_SIDECAR_USER_ID,
                settings.DY_SIDECAR_PROJECT_ID,
                settings.DY_SIDECAR_NODE_ID,
            ),
        )
        await outputs_manager.start()

    async def on_shutdown() -> None:
        outputs_manager: OutputsManager | None = app.state.outputs_manager
        if outputs_manager is not None:
            await outputs_manager.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
