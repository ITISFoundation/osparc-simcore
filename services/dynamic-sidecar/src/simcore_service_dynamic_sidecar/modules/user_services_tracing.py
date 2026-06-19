"""Forwards user-service traces from the shared volume to the platform OTEL collector.

The injected OTEL Collector in user-service compose specs writes spans to a shared
Docker volume using the file exporter with rotation. This module reads the rotated
(immutable) span files and forwards them via HTTP POST to the platform's OTLP endpoint,
then deletes the processed files.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import aiofiles
import aiofiles.os
import httpx
from fastapi import FastAPI, status
from servicelib.background_task import create_periodic_task
from servicelib.fastapi.tracing import get_tracing_config
from servicelib.logging_utils import log_catch
from settings_library.tracing import TracingSettings
from yarl import URL

from ..core.settings import ApplicationSettings, UserServicesTracingSettings
from .mounted_fs import MountedVolumes

_logger = logging.getLogger(__name__)

_ACTIVE_FILE_NAME = "spans.jsonl"
_CHECKPOINT_FILE_NAME = "_trace_offset"


@dataclass
class _TraceBatch:
    """A chunk of trace bytes ready to forward plus how to commit it once sent.

    ``commit`` advances the reader's offset and/or deletes the source file. It must
    be awaited by the caller ONLY after the content has been forwarded successfully.
    """

    content: bytes
    _commit: Callable[[], Awaitable[None]]

    async def commit(self) -> None:
        await self._commit()


class RotatingTraceFileReader:
    """Encapsulates reading the rotating JSONL trace directory.

    Responsibilities:
    - Track a byte offset into the active file so each scrape only forwards new data.
    - Persist/restore that offset via a checkpoint file for crash recovery.
    - Yield only complete (newline-terminated) byte ranges, skipping already-forwarded
      bytes, from rotated (immutable) files first and then the active file.

    Forwarding is intentionally NOT a concern of this class: callers forward each
    batch's content and call ``batch.commit()`` only on success. This keeps the
    byte-offset/rotation bookkeeping isolated and independently testable.
    """

    def __init__(self, traces_directory: Path) -> None:
        self._traces_directory = traces_directory
        self._offset: int = 0

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def _checkpoint_path(self) -> Path:
        return self._traces_directory / _CHECKPOINT_FILE_NAME

    async def restore_offset(self) -> int:
        """Loads the persisted offset from the checkpoint file (0 if missing/invalid)."""
        self._offset = await self._read_checkpoint()
        return self._offset

    async def _read_checkpoint(self) -> int:
        if not await aiofiles.os.path.exists(self._checkpoint_path):
            return 0
        try:
            async with aiofiles.open(self._checkpoint_path) as f:
                content = await f.read()
            return int(content.strip())
        except (ValueError, OSError):
            _logger.warning("Invalid checkpoint file, resetting offset to 0")
            return 0

    async def persist_offset(self) -> None:
        """Atomically persists the current offset to the checkpoint file (tmp + rename)."""
        tmp_path = self._checkpoint_path.with_suffix(f".{uuid4().hex[:8]}.tmp")
        async with aiofiles.open(tmp_path, "w") as f:
            await f.write(f"{self._offset}")
        await aiofiles.os.rename(tmp_path, self._checkpoint_path)

    async def _get_rotated_files(self) -> list[Path]:
        """Returns rotated span files (not the active one), oldest→newest."""
        all_files = await asyncio.to_thread(list, self._traces_directory.glob("spans*.jsonl"))
        return sorted(f for f in all_files if f.name != _ACTIVE_FILE_NAME)

    def _rotated_commit(self, file_path: Path) -> Callable[[], Awaitable[None]]:
        async def _commit() -> None:
            await aiofiles.os.remove(file_path)
            # The file rotated away: the new active file starts at offset 0.
            self._offset = 0
            await self.persist_offset()

        return _commit

    async def iter_pending(self, *, drain: bool) -> AsyncIterator[_TraceBatch]:
        """Yields the trace batches that still need forwarding.

        Rotated (immutable) files are yielded first (oldest→newest), then the active
        file. The offset is consulted lazily, so once the caller commits a rotated
        batch (which resets the offset to 0) subsequent files are read in full.

        When ``drain`` is True the active file is read to its end and deleted on
        commit; otherwise only the complete-line tail is yielded and the file is kept.
        """
        for file_path in await self._get_rotated_files():
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
            # Only send bytes beyond what we already tailed from this (now rotated) file.
            yield _TraceBatch(
                content=content[self._offset :],
                _commit=self._rotated_commit(file_path),
            )

        if drain:
            async for batch in self._iter_active_drain():
                yield batch
        else:
            async for batch in self._iter_active_tail():
                yield batch

    async def _iter_active_tail(self) -> AsyncIterator[_TraceBatch]:
        """Yields new complete lines appended to the active file since the last scrape."""
        active_file = self._traces_directory / _ACTIVE_FILE_NAME
        if not await aiofiles.os.path.exists(active_file):
            return

        stat_result = await aiofiles.os.stat(active_file)
        if stat_result.st_size <= self._offset:
            return

        async with aiofiles.open(active_file, "rb") as f:
            await f.seek(self._offset)
            new_content = await f.read()
        if not new_content:
            return

        # Only forward complete lines (the last line might be partially written).
        last_newline = new_content.rfind(b"\n")
        if last_newline == -1:
            return  # no complete lines yet

        content_to_send = new_content[: last_newline + 1]
        if not content_to_send.strip():
            return

        async def _commit() -> None:
            self._offset += len(content_to_send)

        yield _TraceBatch(content=content_to_send, _commit=_commit)

    async def _iter_active_drain(self) -> AsyncIterator[_TraceBatch]:
        """Yields the remaining un-tailed bytes of the active file and deletes it on commit."""
        active_file = self._traces_directory / _ACTIVE_FILE_NAME
        if not await aiofiles.os.path.exists(active_file):
            return

        async with aiofiles.open(active_file, "rb") as f:
            content = await f.read()

        async def _commit() -> None:
            await aiofiles.os.remove(active_file)
            self._offset = 0
            await self.persist_offset()

        yield _TraceBatch(content=content[self._offset :], _commit=_commit)


class UserServicesTraceForwarder:
    def __init__(
        self,
        traces_directory: Path,
        user_services_tracing_settings: UserServicesTracingSettings,
        platform_tracing_settings: TracingSettings,
    ) -> None:
        self._traces_directory = traces_directory
        self._user_services_tracing_settings = user_services_tracing_settings
        self._reader = RotatingTraceFileReader(traces_directory)
        self._scrape_task: asyncio.Task | None = None

        self._otlp_endpoint = f"{
            URL(f'{platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}')
            .with_port(platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT)
            .with_path('/v1/traces')
        }"
        self._client = httpx.AsyncClient(
            timeout=user_services_tracing_settings.USER_SERVICES_TRACING_FORWARD_TIMEOUT.total_seconds()
        )

    async def setup(self) -> None:
        await self._reader.restore_offset()
        _logger.info(
            "Restored trace forwarder offset from checkpoint: %d",
            self._reader.offset,
        )

        interval = self._user_services_tracing_settings.USER_SERVICES_TRACING_SCRAPE_INTERVAL
        self._scrape_task = create_periodic_task(
            self._scrape_once,
            interval=interval,
            task_name="user_services_trace_forwarder",
        )
        _logger.info(
            "User services trace forwarder started, scraping %s, forwarding to %s",
            self._traces_directory,
            self._otlp_endpoint,
        )

    async def shutdown(self) -> None:
        if self._scrape_task is not None:
            self._scrape_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scrape_task
            self._scrape_task = None
        await self._client.aclose()

    async def drain_remaining_traces(self) -> None:
        """Drains all remaining trace files after user services have stopped."""
        timeout = self._user_services_tracing_settings.USER_SERVICES_TRACING_DRAIN_TIMEOUT.total_seconds()
        _logger.info("Draining remaining trace files (timeout=%.1fs)", timeout)
        try:
            await asyncio.wait_for(self._forward_pending(drain=True), timeout=timeout)
        except TimeoutError:
            _logger.warning("Drain timeout reached, some traces may be lost")

    async def _scrape_once(self) -> None:
        with log_catch(_logger, reraise=False):
            await self._forward_pending(drain=False)
            # Persist current offset for crash recovery
            await self._reader.persist_offset()

    async def _forward_pending(self, *, drain: bool) -> None:
        """Forwards every pending batch, committing each only after a successful send.

        Stops on the first failed send so the unsent file(s) are kept for retry and
        the offset is not advanced past data that never reached the platform.
        """
        async for batch in self._reader.iter_pending(drain=drain):
            if batch.content and not await self._forward_content(batch.content):
                break  # keep file for retry
            await batch.commit()

    async def _forward_content(self, content: bytes) -> bool:
        """Forwards content to the platform OTLP endpoint. Returns True on success."""
        max_batch_size = self._user_services_tracing_settings.USER_SERVICES_TRACING_MAX_BATCH_SIZE

        chunks: list[bytes]
        if len(content) <= max_batch_size:
            chunks = [content]
        else:
            lines = content.split(b"\n")
            chunks = []
            current_chunk = b""
            for line in lines:
                if not line:
                    continue
                if current_chunk and len(current_chunk) + len(line) + 1 > max_batch_size:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk = current_chunk + b"\n" + line if current_chunk else line
            if current_chunk:
                chunks.append(current_chunk)

        for chunk in chunks:
            try:
                response = await self._client.post(
                    self._otlp_endpoint, content=chunk, headers={"Content-Type": "application/json"}
                )
                if response.status_code != status.HTTP_200_OK:
                    _logger.warning("Failed to forward traces: HTTP %d", response.status_code)
                    return False
            except httpx.HTTPError:
                _logger.warning("Failed to forward traces", exc_info=True)
                return False

        return True


def setup_user_services_tracing(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings
    platform_tracing_settings = settings.DYNAMIC_SIDECAR_TRACING
    assert platform_tracing_settings is not None  # nosec

    mounted_volumes: MountedVolumes = app.state.mounted_volumes

    app.state.user_services_trace_forwarder = forwarder = UserServicesTraceForwarder(
        traces_directory=mounted_volumes.disk_traces_path,
        user_services_tracing_settings=settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG,
        platform_tracing_settings=platform_tracing_settings,
    )

    async def on_startup() -> None:
        await forwarder.setup()

    async def on_shutdown() -> None:
        await forwarder.drain_remaining_traces()
        await forwarder.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_user_services_trace_forwarder(app: FastAPI) -> UserServicesTraceForwarder:
    assert isinstance(app.state.user_services_trace_forwarder, UserServicesTraceForwarder)  # nosec
    return app.state.user_services_trace_forwarder


def is_user_services_tracing_enabled(app: FastAPI) -> bool:
    settings: ApplicationSettings = app.state.settings
    tracing_config = get_tracing_config(app)
    return tracing_config.tracing_enabled and settings.DY_SIDECAR_USER_SERVICES_TRACING_OPT_IN
