import asyncio
import logging
import os
import time
from asyncio import CancelledError, Future, Lock, Task, create_task, wait
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import timedelta
from functools import partial
from typing import Annotated, Final, NamedTuple

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
from ._content_monitor import DEFAULT_HASH_WORKERS, PortContentMonitor, StabilityOutcome
from ._context import OutputsContext
from ._upload_trust import PortUploadTrust

_logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_S: Final[
    Annotated[PositiveFloat, doc("background content re-check period catching lost filesystem events")]
] = 60.0


async def _cancel_task(task: Task, task_cancellation_timeout_s: PositiveFloat) -> None:
    task.cancel("cancelling task")
    with suppress(CancelledError), log_catch(_logger, reraise=False):
        await wait((task,), timeout=task_cancellation_timeout_s)


def _log_unawaited_task_exception(future: Task[None]) -> None:
    """Logs an exception no one awaited, instead of losing it to a garbage-collection warning"""
    if future.cancelled():
        return
    if (exception := future.exception()) is not None:
        _logger.warning("task %s failed: %s", future.get_name(), exception, exc_info=exception)


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


class _PortWatch(NamedTuple):
    """Per-port pair: content monitor and upload certification"""

    monitor: PortContentMonitor
    trust: PortUploadTrust


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
        background_uploads_enabled: bool = False,
    ):
        self.outputs_context = outputs_context
        self.port_notifier = port_notifier
        self.io_log_redirect_cb = io_log_redirect_cb
        self.upload_upon_api_request = upload_upon_api_request
        self.task_cancellation_timeout_s = task_cancellation_timeout_s
        self.task_monitor_interval_s = task_monitor_interval_s
        self.task_progress_cb = progress_cb

        self._port_key_tracker = _PortKeyTracker()
        self._hash_executor = ThreadPoolExecutor(max_workers=DEFAULT_HASH_WORKERS, thread_name_prefix="outputs_content")
        self._port_watches: dict[str, _PortWatch] = {}
        self._task_uploading: Task | None = None
        self._task_uploading_followup: Task | None = None
        self._task_scheduler_worker: Task | None = None
        self._task_sweep: Task | None = None
        self._next_sweep_mono: float = 0.0
        self._sweep_forced: bool = False
        # output IO starts disabled (container creation pending), like the watchdog handler
        self._background_uploads_enabled: bool = background_uploads_enabled

        # keep track if a port was uploaded and there was an error, remove said error if last upload was ok
        self._last_upload_error_tracker: dict[str, str | None] = {}

    def _get_port_watch(self, port_key: str) -> _PortWatch | None:
        if port_key not in self.outputs_context.file_type_port_keys:
            return None
        watch = self._port_watches.get(port_key)
        if watch is None:
            monitor = PortContentMonitor(
                port_key=port_key,
                directory=self.outputs_context.outputs_path / port_key,
                hash_executor=self._hash_executor,
                on_stable_content=self._on_stable_content,
            )
            watch = _PortWatch(monitor=monitor, trust=PortUploadTrust(port_key=port_key, monitor=monitor))
            self._port_watches[port_key] = watch
        return watch

    def on_port_key_change(self, port_key: str) -> None:
        """called on filesystem activity for a port: (re)starts the quiet countdown"""
        watch = self._get_port_watch(port_key)
        if watch is None:
            _logger.debug("port key %s changed but is not a file port: ignored", port_key)
            return
        watch.monitor.record_filesystem_event()

    def set_background_uploads_enabled(self, *, is_enabled: bool) -> None:
        """Background scheduling follows the output-IO state; explicit saves stay ungated"""
        if is_enabled and not self._background_uploads_enabled:
            self._sweep_forced = True  # content may have changed while disabled: re-check everything
        self._background_uploads_enabled = is_enabled

    async def _on_stable_content(self, port_key: str, fingerprint: str) -> None:
        """a quiet-proven fingerprint: schedule the upload unless that content is already certified"""
        if not self._background_uploads_enabled:
            _logger.info("port %s: output IO disabled, the sweep on re-enable will retry this check", port_key)
            return
        if (watch := self._get_port_watch(port_key)) is not None and watch.trust.is_certified(fingerprint):
            return  # identical content to the last successful upload: nothing left to send
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
            if (watch := self._get_port_watch(port_key)) is None:
                continue
            # capture the candidate as late as possible: it is what the PUT is about to send
            if (candidate := watch.monitor.stable_fingerprint()) is not None:
                watch.trust.note_upload_started(candidate)
            else:
                # this PUT archives content the scan could not identify, so it certifies nothing
                watch.trust.note_upload_uncertified()

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

            self._task_uploading_followup = create_task(
                self._uploaded_ports_followup(port_keys, failed_port_keys), name="outputs_upload_followup"
            )
            self._task_uploading_followup.add_done_callback(_log_unawaited_task_exception)

        self._task_uploading.add_done_callback(_remove_downloads)

    async def _uploaded_ports_followup(self, port_keys: list[str], failed_port_keys: set[str]) -> None:
        rearm_port_keys: set[str] = set()
        try:
            for port_key in port_keys:
                if port_key in failed_port_keys:
                    continue  # the sweep retries it after the content goes quiet
                watch = self._get_port_watch(port_key)
                if watch is None:
                    continue
                with log_catch(_logger, reraise=False):
                    if not await watch.trust.verify_upload_completed():
                        _logger.info("Port %s changed during upload, waiting for it to settle", port_key)
                        rearm_port_keys.add(port_key)

            # re-arm first: a waiter must not see a cleared tracker with a check pending
            for port_key in rearm_port_keys:
                watch = self._get_port_watch(port_key)
                if watch is None:
                    continue
                # the PUT stored bytes no scan verified: the previous certification is void
                watch.trust.note_upload_uncertified()
                watch.monitor.record_filesystem_event()
        finally:
            # the uploading set must never outlive this task: it blocks every later upload
            await self._port_key_tracker.remove_all_uploading()

    async def _uploading_task_cancel(self) -> None:
        if self._task_uploading is not None:
            await _cancel_task(self._task_uploading, self.task_cancellation_timeout_s)
            await self._port_key_tracker.move_all_uploading_to_pending()
            self._task_uploading = None
        if self._task_uploading_followup is not None:
            await _cancel_task(self._task_uploading_followup, self.task_cancellation_timeout_s)
            self._task_uploading_followup = None

    def _port_directory_has_content(self, port_key: str) -> bool:
        try:
            with os.scandir(self.outputs_context.outputs_path / port_key) as entries:
                return next(entries, None) is not None
        except FileNotFoundError:
            return False
        except OSError:
            # unreadable counts as content: the scan reports it instead of skipping the port
            return True

    async def _run_safety_sweep(self) -> None:
        uploading_port_keys = await self._port_key_tracker.get_uploading()
        try:
            for port_key in self.outputs_context.file_type_port_keys:
                if not self._background_uploads_enabled:
                    break  # output IO disabled mid-sweep: re-enabling forces a new sweep
                if port_key in uploading_port_keys:
                    continue
                if port_key not in self._port_watches and not self._port_directory_has_content(port_key):
                    continue  # an untracked empty port has nothing to discover
                # a lost first notification must not leave the port invisible to every later sweep
                if (watch := self._get_port_watch(port_key)) is None:
                    continue
                with log_catch(_logger, reraise=False):
                    await watch.monitor.sweep()
        finally:
            self._next_sweep_mono = time.monotonic() + _SWEEP_INTERVAL_S

    def _start_safety_sweep(self) -> None:
        if self._task_sweep is not None and not self._task_sweep.done():
            return  # a forced request keeps its flag set: it runs as soon as the in-flight sweep ends
        # the sweep task runs beside the scheduler tick: a slow mount cannot delay uploads
        self._sweep_forced = False
        self._task_sweep = create_task(self._run_safety_sweep(), name="outputs_safety_sweep")
        self._task_sweep.add_done_callback(_log_unawaited_task_exception)

    async def _scheduler_worker(self) -> None:
        if self._background_uploads_enabled and (self._sweep_forced or time.monotonic() >= self._next_sweep_mono):
            self._start_safety_sweep()

        if await self._port_key_tracker.are_pending_ports_uploading():
            await self._uploading_task_cancel()
            await self._port_key_tracker.move_all_uploading_to_pending()

        # pending port keys carry a finished decision (quiet check or save path): schedule them
        schedulable_port_keys = await self._port_key_tracker.get_pending()
        if schedulable_port_keys and await self._port_key_tracker.can_schedule_ports_to_upload():
            await self._port_key_tracker.move_to_uploading(*sorted(schedulable_port_keys))

            await self._uploading_task_start()

    def set_all_ports_for_upload(self) -> None:
        _logger.warning("watchdog restarted: outputs events were lost, running a safety sweep on the next tick")
        self._sweep_forced = True

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
            if self._task_sweep is not None:
                await _cancel_task(self._task_sweep, self.task_cancellation_timeout_s)
            for watch in self._port_watches.values():
                watch.monitor.shutdown()
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

        # a save uploads now: check every port without waiting for quiet
        for file_port_key in self.outputs_context.file_type_port_keys:
            watch = self._get_port_watch(file_port_key)
            assert watch is not None  # nosec
            result = await watch.monitor.check_now()
            if result.outcome is StabilityOutcome.STABLE and watch.trust.is_certified(result.fingerprint):
                _logger.info("Skipping upload of port %s: content matches the last successful upload", file_port_key)
            else:
                if result.outcome is StabilityOutcome.UNSTABLE:
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
        if self._task_sweep is not None and not self._task_sweep.done():
            return False  # a running sweep can still schedule an upload
        if not await self._port_key_tracker.no_tracked_ports():
            return False
        file_port_keys = set(self.outputs_context.file_type_port_keys)
        return not any(
            watch.monitor.has_pending_work()
            for port_key, watch in self._port_watches.items()
            if port_key in file_port_keys
        )

    def _in_flight_upload_round_running(self) -> bool:
        return (self._task_uploading is not None and not self._task_uploading.done()) or (
            self._task_uploading_followup is not None and not self._task_uploading_followup.done()
        )

    async def _wait_in_flight_upload_round(self) -> None:
        """Waits for the current upload task and its follow-up verification, if any are running"""
        while self._in_flight_upload_round_running():  # noqa: ASYNC110
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
