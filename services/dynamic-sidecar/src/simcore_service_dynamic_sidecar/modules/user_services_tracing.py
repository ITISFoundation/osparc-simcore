"""Forwards user-service traces from the shared volume to the platform OTEL collector.

The injected OTEL Collector in user-service compose specs writes spans to a shared
Docker volume using the file exporter with rotation. This module reads the rotated
(immutable) span files and forwards them via HTTP POST to the platform's OTLP endpoint,
then deletes the processed files.
"""

import asyncio
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI
from settings_library.tracing import TracingSettings
from yarl import URL

from ..core.settings import ApplicationSettings, UserServiceTracingSettings
from .mounted_fs import MountedVolumes

_logger = logging.getLogger(__name__)

_ACTIVE_FILE_NAME = "spans.jsonl"


class UserServicesTraceForwarder:
    def __init__(
        self,
        traces_directory: Path,
        tracing_settings: UserServiceTracingSettings,
        platform_tracing_settings: TracingSettings,
    ) -> None:
        self._traces_directory = traces_directory
        self._tracing_settings = tracing_settings
        self._scrape_task: asyncio.Task | None = None

        endpoint = f"{
            URL(f'{platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}')
            .with_port(platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT)
            .with_path('/v1/traces')
        }"
        self._otlp_endpoint = endpoint
        self._client = httpx.AsyncClient(timeout=30.0)

    async def start(self) -> None:
        self._scrape_task = asyncio.create_task(self._scrape_loop(), name="user_services_trace_forwarder")
        _logger.info("User services trace forwarder started")

    async def stop(self) -> None:
        if self._scrape_task is not None:
            self._scrape_task.cancel()
            try:
                await self._scrape_task
            except asyncio.CancelledError:
                pass
            self._scrape_task = None
        await self._client.aclose()

    async def drain_remaining_traces(self) -> None:
        """Drains all remaining trace files after user services have stopped."""
        timeout = self._tracing_settings.USER_SERVICES_TRACING_DRAIN_TIMEOUT_S
        _logger.info("Draining remaining trace files (timeout=%.1fs)", timeout)
        try:
            await asyncio.wait_for(self._forward_all_files(), timeout=timeout)
        except TimeoutError:
            _logger.warning("Drain timeout reached, some traces may be lost")

    async def _scrape_loop(self) -> None:
        interval = self._tracing_settings.USER_SERVICES_TRACING_SCRAPE_INTERVAL_S
        while True:
            try:
                await self._forward_rotated_files()
            except Exception:
                _logger.exception("Error forwarding trace files")
            await asyncio.sleep(interval)

    async def _forward_rotated_files(self) -> None:
        """Forwards only rotated (immutable) files, skipping the active file."""
        for file_path in self._get_rotated_files():
            await self._forward_and_delete(file_path)

    async def _forward_all_files(self) -> None:
        """Forwards ALL files including the active one (used during drain)."""
        for file_path in sorted(self._traces_directory.glob("spans*.jsonl")):
            await self._forward_and_delete(file_path)

    def _get_rotated_files(self) -> list[Path]:
        """Returns rotated span files (not the active one)."""
        return sorted(f for f in self._traces_directory.glob("spans*.jsonl") if f.name != _ACTIVE_FILE_NAME)

    async def _forward_and_delete(self, file_path: Path) -> None:
        max_batch_size = self._tracing_settings.USER_SERVICES_TRACING_MAX_BATCH_SIZE
        content = file_path.read_bytes()
        if not content:
            file_path.unlink(missing_ok=True)
            return

        # Split into chunks if file exceeds max batch size
        if len(content) <= max_batch_size:
            chunks = [content]
        else:
            lines = content.split(b"\n")
            chunks: list[bytes] = []
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
                    self._otlp_endpoint,
                    content=chunk,
                    headers={"Content-Type": "application/json"},
                )
                if response.status_code >= 400:
                    _logger.warning(
                        "Failed to forward traces from %s: HTTP %d",
                        file_path.name,
                        response.status_code,
                    )
                    return  # keep file for retry
            except httpx.HTTPError:
                _logger.warning(
                    "Failed to forward traces from %s",
                    file_path.name,
                    exc_info=True,
                )
                return  # keep file for retry

        file_path.unlink(missing_ok=True)
        _logger.debug("Forwarded and deleted %s", file_path.name)


def setup_user_services_tracing(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        tracing_settings = settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING
        platform_tracing_settings = settings.DYNAMIC_SIDECAR_TRACING
        assert tracing_settings is not None  # nosec
        assert platform_tracing_settings is not None  # nosec

        mounted_volumes: MountedVolumes = app.state.mounted_volumes

        app.state.user_services_trace_forwarder = forwarder = UserServicesTraceForwarder(
            traces_directory=mounted_volumes.disk_traces_path,
            tracing_settings=tracing_settings,
            platform_tracing_settings=platform_tracing_settings,
        )
        await forwarder.start()

    async def on_shutdown() -> None:
        forwarder: UserServicesTraceForwarder = app.state.user_services_trace_forwarder
        await forwarder.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
