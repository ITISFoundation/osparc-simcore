"""Forwards user-service traces from the shared volume to the platform OTEL collector.

The injected OTEL Collector in user-service compose specs writes spans to a shared
Docker volume using the file exporter with rotation. This module reads the rotated
(immutable) span files and forwards them via HTTP POST to the platform's OTLP endpoint,
then deletes the processed files.
"""

import asyncio
import contextlib
import logging
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


class UserServicesTraceForwarder:
    def __init__(
        self,
        traces_directory: Path,
        user_services_tracing_settings: UserServicesTracingSettings,
        platform_tracing_settings: TracingSettings,
    ) -> None:
        self._traces_directory = traces_directory
        self._user_services_tracing_settings = user_services_tracing_settings
        self._scrape_task: asyncio.Task | None = None
        self._active_file_offset: int = 0

        self._otlp_endpoint = f"{
            URL(f'{platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}')
            .with_port(platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT)
            .with_path('/v1/traces')
        }"
        self._client = httpx.AsyncClient(
            timeout=user_services_tracing_settings.USER_SERVICES_TRACING_FORWARD_TIMEOUT.total_seconds()
        )

    @property
    def _checkpoint_path(self) -> Path:
        return self._traces_directory / _CHECKPOINT_FILE_NAME

    async def _read_checkpoint(self) -> int:
        """Reads persisted offset from checkpoint file. Returns 0 if missing or invalid."""
        if not await aiofiles.os.path.exists(self._checkpoint_path):
            return 0
        try:
            async with aiofiles.open(self._checkpoint_path) as f:
                content = await f.read()
            return int(content.strip())
        except (ValueError, OSError):
            _logger.warning("Invalid checkpoint file, resetting offset to 0")
            return 0

    async def _write_checkpoint(self, offset: int) -> None:
        """Atomically persists offset to checkpoint file (tmp + rename)."""
        tmp_path = self._checkpoint_path.with_suffix(f".{uuid4().hex[:8]}.tmp")
        async with aiofiles.open(tmp_path, "w") as f:
            await f.write(f"{offset}")
        await aiofiles.os.rename(tmp_path, self._checkpoint_path)

    async def setup(self) -> None:
        self._active_file_offset = await self._read_checkpoint()
        _logger.info(
            "Restored trace forwarder offset from checkpoint: %d",
            self._active_file_offset,
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
            await asyncio.wait_for(self._forward_all_files(), timeout=timeout)
        except TimeoutError:
            _logger.warning("Drain timeout reached, some traces may be lost")

    async def _scrape_once(self) -> None:
        with log_catch(_logger, reraise=False):
            # Forward completed rotated files first
            rotated_files = await self._get_rotated_files()
            if rotated_files:
                _logger.info(
                    "Scrape cycle: found %d rotated trace file(s) to forward",
                    len(rotated_files),
                )
            for file_path in rotated_files:
                await self._forward_rotated_file(file_path)

            # Also forward new data from the active file
            await self._forward_active_file_tail()

            # Persist current offset for crash recovery
            await self._write_checkpoint(self._active_file_offset)

    async def _forward_active_file_tail(self) -> None:
        """Reads new bytes appended to the active file since last scrape and forwards them."""
        active_file = self._traces_directory / _ACTIVE_FILE_NAME
        if not await aiofiles.os.path.exists(active_file):
            return

        stat_result = await aiofiles.os.stat(active_file)
        if stat_result.st_size <= self._active_file_offset:
            return

        async with aiofiles.open(active_file, "rb") as f:
            await f.seek(self._active_file_offset)
            new_content = await f.read()

        if not new_content:
            return

        # Only forward complete lines (the last line might be partially written)
        last_newline = new_content.rfind(b"\n")
        if last_newline == -1:
            return  # no complete lines yet

        content_to_send = new_content[: last_newline + 1]
        if not content_to_send.strip():
            return

        success = await self._forward_content(content_to_send)
        if success:
            self._active_file_offset += len(content_to_send)
            _logger.info(
                "Forwarded %d bytes from active file (offset now %d)",
                len(content_to_send),
                self._active_file_offset,
            )

    async def _forward_rotated_file(self, file_path: Path) -> None:
        """Forwards only the un-tailed portion of a rotated file and deletes it.

        When the active file rotates, we may have already forwarded some bytes
        via _forward_active_file_tail. Only send the remainder to avoid duplicates.
        """
        async with aiofiles.open(file_path, "rb") as f:
            content = await f.read()
        if not content:
            await aiofiles.os.remove(file_path)
            self._active_file_offset = 0
            return

        # Only send bytes beyond what we already tailed
        unsent_content = content[self._active_file_offset :]
        skipped_bytes = self._active_file_offset
        if unsent_content and not await self._forward_content(unsent_content):
            return  # keep file for retry

        await aiofiles.os.remove(file_path)
        # Reset offset for the new active file and persist
        self._active_file_offset = 0
        await self._write_checkpoint(0)
        _logger.info(
            "Forwarded and deleted %s (sent %d of %d bytes, skipped %d already-tailed)",
            file_path.name,
            len(unsent_content),
            len(content),
            skipped_bytes,
        )

    async def _forward_rotated_files(self) -> None:
        """Forwards only rotated (immutable) files, skipping the active file."""
        for file_path in await self._get_rotated_files():
            await self._forward_rotated_file(file_path)

    async def _forward_all_files(self) -> None:
        """Forwards ALL files including the active one (used during drain).

        Offset-aware: skips already-tailed bytes to avoid duplicates.
        Processes rotated files first (oldest→newest), then the active file.
        """
        rotated_files = await self._get_rotated_files()
        for file_path in rotated_files:
            await self._forward_rotated_file(file_path)

        # Forward remaining content from the active file
        active_file = self._traces_directory / _ACTIVE_FILE_NAME
        if await aiofiles.os.path.exists(active_file):
            async with aiofiles.open(active_file, "rb") as f:
                content = await f.read()
            unsent = content[self._active_file_offset :]
            if unsent and not await self._forward_content(unsent):
                return
            await aiofiles.os.remove(active_file)
            self._active_file_offset = 0
            await self._write_checkpoint(0)

    async def _get_rotated_files(self) -> list[Path]:
        """Returns rotated span files (not the active one)."""
        all_files = await asyncio.to_thread(list, self._traces_directory.glob("spans*.jsonl"))
        return sorted(f for f in all_files if f.name != _ACTIVE_FILE_NAME)

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
        user_services_tracing_settings=settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_SETTINGS,
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
    return tracing_config.tracing_enabled and settings.DY_SIDECAR_USER_SERVICES_TRACING_ENABLED
