import asyncio
import logging
import time
from asyncio import CancelledError, Future, Lock, Task, create_task, wait
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import timedelta
from functools import partial
from typing import Annotated, Final

from annotated_types import doc
from common_library.async_tools import cancel_wait_task
from common_library.errors_classes import OsparcErrorMixin
from common_library.logging.logging_errors import (
    create_troubleshooting_log_kwargs,
    format_exception_as_string,
)
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from models_library.rabbitmq_messages import ProgressType
from pydantic import PositiveFloat
from servicelib import progress_bar
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_catch, log_context
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB

from ...core.rabbitmq import post_log_message, post_progress_message
from ...core.settings import ApplicationSettings
from ...modules.notifications._notifications_ports import PortNotifier
from ..nodeports import upload_outputs
from ._context import OutputsContext
from ._fingerprinter import DEFAULT_HASH_WORKERS, CheckOutcome, PortFingerprint

_logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_S: Final[
    Annotated[PositiveFloat, doc("background content re-check period catching lost filesystem events")]
] = 60.0


async def _cancel_task(task: Task, task_cancellation_timeout_s: PositiveFloat) -> None:
    task.cancel("cancelling task")
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
        return f"pending={self._pending_port_keys} uploading={self._uploading_port_keys}"

    async def add_pending(self, port_key: str) -> None:
        async with self._lock:
            self._pending_port_keys.add(port_key)

    async def add_pending_unless_uploading(self, port_key: str) -> bool:
        """Schedules the port unless an upload of it is in flight; reports whether it scheduled"""
        async with self._lock:
            if port_key in self._uploading_port_keys:
                return False
            self._pending_port_keys.add(port_key)
            return True

    async def are_pending_ports_uploading(self) -> bool:
        async with self._lock:
            return len(self._pending_port_keys & self._uploading_port_keys) > 0

    async def can_schedule_ports_to_upload(self) -> bool:
        async with self._lock:
            return len(self._uploading_port_keys) == 0 and len(self._pending_port_keys) > 0

    async def no_tracked_ports(self) -> bool:
        async with self._lock:
            return len(self._pending_port_keys) == 0 and len(self._uploading_port_keys) == 0

    async def move_all_ports_to_uploading(self) -> None:
        async with self._lock:
            self._uploading_port_keys.update(self._pending_port_keys)
            self._pending_port_keys.clear()

    async def get_uploading(self) -> list[str]:
        async with self._lock:
            return list(self._uploading_port_keys)

    async def get_pending(self) -> set[str]:
        async with self._lock:
            return self._pending_port_keys

    async def remove_pending(self, *port_keys: str) -> None:
        async with self._lock:
            self._pending_port_keys.difference_update(port_keys)

    async def move_to_uploading(self, *port_keys: str) -> None:
        async with self._lock:
            self._uploading_port_keys.update(port_keys)
            self._pending_port_keys.difference_update(port_keys)

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
        self._hash_executor = ThreadPoolExecutor(
            max_workers=DEFAULT_HASH_WORKERS, thread_name_prefix="outputs_fingerprint"
        )
        self._fingerprints: dict[str, PortFingerprint] = {}
        self._task_uploading: Task | None = None
        self._task_uploading_followup: Task | None = None
        self._task_scheduler_worker: Task | None = None
        self._next_sweep_mono: float = 0.0

        # keep track if a port was uploaded and there was an error, remove said error if last upload was ok
        self._last_upload_error_tracker: dict[str, str | None] = {}

    def _get_fingerprint(self, port_key: str) -> PortFingerprint | None:
        if port_key not in self.outputs_context.file_type_port_keys:
            return None
        fingerprint = self._fingerprints.get(port_key)
        if fingerprint is None:
            fingerprint = PortFingerprint(
                port_key=port_key,
                directory=self.outputs_context.outputs_path / port_key,
                hash_executor=self._hash_executor,
                on_stable_change=self._on_stable_change,
            )
            self._fingerprints[port_key] = fingerprint
        return fingerprint

    def on_port_key_change(self, port_key: str) -> None:
        """called on filesystem activity for a port: (re)starts the quiet countdown"""
        fingerprint = self._get_fingerprint(port_key)
        if fingerprint is None:
            _logger.debug("port key %s changed but is not a file port: ignored", port_key)
            return
        fingerprint.note_event()

    async def _on_stable_change(self, port_key: str) -> None:
        """a quiet-proven fingerprint differing from the last upload: schedule the upload"""
        if not await self._port_key_tracker.add_pending_unless_uploading(port_key):
            _logger.info(
                "port %s: new content while an upload is in flight, the post-upload check picks it up", port_key
            )
            return
        _logger.info("port %s: quiet content differs from the last upload, scheduling upload", port_key)

    async def _uploading_task_start(self) -> None:
        port_keys = await self._port_key_tracker.get_uploading()
        assert len(port_keys) > 0  # nosec

        for port_key in port_keys:
            if (fingerprint := self._get_fingerprint(port_key)) is None:
                continue
            # capture the candidate as late as possible: it is what the PUT is about to send
            if (candidate := fingerprint.take_upload_candidate()) is not None:
                fingerprint.note_upload_started(candidate)

        async def _upload_ports() -> None:
            with log_context(_logger, logging.INFO, f"Uploading port keys: {port_keys}"):
                async with progress_bar.ProgressBarData(
                    num_steps=1,
                    progress_report_cb=self.task_progress_cb,
                    description="uploading ports",
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
            exception = future._exception  # noqa: SLF001 # pylint: disable=protected-access
            if exception is not None:
                _logger.warning(
                    **create_troubleshooting_log_kwargs(
                        f"{task_name} ended with exception: {exception}\n{format_exception_as_string(exception)}",
                        error=exception,
                        error_context={
                            "port_keys": port_keys,
                            "outputs_path": self.outputs_context.outputs_path,
                        },
                    )
                )

            # keep track of the last result for each port
            failed_port_keys: set[str] = set()
            for port_key in port_keys:
                try:
                    future.result()
                    self._last_upload_error_tracker[port_key] = None
                except Exception as e:  # pylint: disable=broad-except
                    self._last_upload_error_tracker[port_key] = format_exception_as_string(e)
                    failed_port_keys.add(port_key)

            self._task_uploading_followup = create_task(self._uploaded_ports_followup(port_keys, failed_port_keys))

        self._task_uploading.add_done_callback(_remove_downloads)

    async def _uploaded_ports_followup(self, port_keys: list[str], failed_port_keys: set[str]) -> None:
        rearm_port_keys: set[str] = set()
        for port_key in port_keys:
            if port_key in failed_port_keys:
                continue  # the safety sweep retries unuploaded content once the port quiets down
            fingerprint = self._get_fingerprint(port_key)
            if fingerprint is None:
                continue
            if not await fingerprint.verify_upload_completed():
                _logger.info("Port %s changed during upload, waiting for it to settle", port_key)
                rearm_port_keys.add(port_key)

        # re-arm first: a waiter must not see a cleared tracker with an episode pending
        for port_key in rearm_port_keys:
            (fingerprint := self._get_fingerprint(port_key)).note_event()  # type: ignore[union-attr]

        await self._port_key_tracker.remove_all_uploading()

    async def _uploading_task_cancel(self) -> None:
        if self._task_uploading is not None:
            await _cancel_task(self._task_uploading, self.task_cancellation_timeout_s)
            await self._port_key_tracker.move_all_uploading_to_pending()
            self._task_uploading = None
        if self._task_uploading_followup is not None:
            await _cancel_task(self._task_uploading_followup, self.task_cancellation_timeout_s)
            self._task_uploading_followup = None

    async def _run_safety_sweep(self) -> None:
        uploading_port_keys = await self._port_key_tracker.get_uploading()
        for port_key, fingerprint in self._fingerprints.items():
            if port_key in uploading_port_keys:
                continue
            with log_catch(_logger, reraise=False):
                await fingerprint.sweep()

    async def _scheduler_worker(self) -> None:
        now = time.monotonic()
        if now >= self._next_sweep_mono:
            self._next_sweep_mono = now + _SWEEP_INTERVAL_S
            await self._run_safety_sweep()

        if await self._port_key_tracker.are_pending_ports_uploading():
            await self._uploading_task_cancel()
            await self._port_key_tracker.move_all_uploading_to_pending()

        # pending port keys carry a finished decision (quiet check or save path): schedule them
        schedulable_port_keys = await self._port_key_tracker.get_pending()
        if schedulable_port_keys and await self._port_key_tracker.can_schedule_ports_to_upload():
            await self._port_key_tracker.move_to_uploading(*sorted(schedulable_port_keys))

            await self._uploading_task_start()

    def set_all_ports_for_upload(self) -> None:
        """watchdog was rebooted: its events were lost, run a safety sweep on the next tick"""
        _logger.warning("watchdog restarted, scheduling an immediate outputs safety sweep")
        self._next_sweep_mono = 0.0

    async def start(self) -> None:
        self._task_scheduler_worker = create_periodic_task(
            self._scheduler_worker,
            interval=timedelta(seconds=self.task_monitor_interval_s),
            task_name="outputs_manager_scheduler_worker",
        )

    async def shutdown(self) -> None:
        with log_context(_logger, logging.INFO, f"{OutputsManager.__name__} shutdown"):
            await self._uploading_task_cancel()
            if self._task_scheduler_worker is not None:
                await cancel_wait_task(self._task_scheduler_worker, max_delay=self.task_monitor_interval_s)
            for fingerprint in self._fingerprints.values():
                fingerprint.shutdown()
            self._hash_executor.shutdown(wait=False, cancel_futures=True)

    async def port_key_content_changed(self, port_key: str) -> None:
        """schedules `port_key` for upload on the next tick; no check is performed here"""
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

        # let an in-flight upload record first: its verification decides the remaining save work
        await self._wait_in_flight_upload_round()

        # save means upload now: check each port without quiet and upload all not proven uploaded
        for file_port_key in self.outputs_context.file_type_port_keys:
            fingerprint = self._get_fingerprint(file_port_key)
            assert fingerprint is not None  # nosec
            outcome = await fingerprint.check_now()
            if outcome is CheckOutcome.STABLE_MATCHING:
                _logger.info("Skipping upload of port %s: content matches the last successful upload", file_port_key)
            else:
                if outcome is CheckOutcome.UNSTABLE:
                    _logger.warning(
                        "port %s content is still moving at save time, uploading the current state", file_port_key
                    )
                await self.port_key_content_changed(file_port_key)

        _logger.info("Port status before waiting %s", f"{self._port_key_tracker}")
        while not await self._no_outputs_work_left():  # noqa: ASYNC110
            await asyncio.sleep(self.task_monitor_interval_s)
        _logger.info("Port status after waiting %s", f"{self._port_key_tracker}")

        # NOTE: checking if there were any errors during the last port upload,
        # for each port. If any error is detected this will raise.
        any_failed_upload = any(True for v in self._last_upload_error_tracker.values() if v is not None)
        if any_failed_upload:
            raise UploadPortsFailedError(failures=self._last_upload_error_tracker)  # pyright: ignore[reportCallIssue]

    async def _no_outputs_work_left(self) -> bool:
        if not await self._port_key_tracker.no_tracked_ports():
            return False
        file_port_keys = set(self.outputs_context.file_type_port_keys)
        return not any(
            fingerprint.has_pending_work()
            for port_key, fingerprint in self._fingerprints.items()
            if port_key in file_port_keys
        )

    async def _in_flight_upload_round_running(self) -> bool:
        return (self._task_uploading is not None and not self._task_uploading.done()) or (
            self._task_uploading_followup is not None and not self._task_uploading_followup.done()
        )

    async def _wait_in_flight_upload_round(self) -> None:
        """Waits for the current upload task and its follow-up verification, if any are running"""
        while await self._in_flight_upload_round_running():  # noqa: ASYNC110
            await asyncio.sleep(self.task_monitor_interval_s)


def configure_outputs_manager(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        outputs_manager: OutputsManager | None = None
        try:
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
                progress_cb=partial(post_progress_message, app, ProgressType.SERVICE_OUTPUTS_PUSHING),
                port_notifier=PortNotifier(
                    app,
                    settings.DY_SIDECAR_USER_ID,
                    settings.DY_SIDECAR_PROJECT_ID,
                    settings.DY_SIDECAR_NODE_ID,
                ),
            )
            await outputs_manager.start()
            yield
        finally:
            if outputs_manager is not None:
                await outputs_manager.shutdown()

    app_lifespan.add(_lifespan)
