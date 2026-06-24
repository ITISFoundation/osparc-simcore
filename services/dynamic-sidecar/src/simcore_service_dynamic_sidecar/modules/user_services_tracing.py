"""Ships user-service traces to the platform OTEL collector via a sidecar collector container.

Instead of forwarding spans in Python, the dynamic-sidecar runs a small **OTEL Collector
container** ("trace shipper") whose only job is to read the OTLP-JSON span files written to
the shared ``/traces`` volume by the *injected* collector (see ``core/validation.py``) and
push them to the platform's OTLP/HTTP endpoint.

Why a container instead of custom code: the collector already solves — robustly — every hard
part we would otherwise hand-roll (tailing the live file, following it across rotation,
batching, retry/backoff, restart resumption).

Lifecycle & ownership:

* The shipper is **created** when the user services start and **removed** when they are
  removed (hooked from ``modules/long_running_tasks.py``). Both operations are idempotent.
* Between those two events Docker keeps it alive: it runs with ``RestartPolicy=unless-stopped``,
  so a crash (or daemon restart) brings it back with no supervision from the sidecar.
* It shares the sidecar's network namespace (``network_mode: container:<sidecar>``), so it
  reaches the platform collector with the exact same DNS/egress the sidecar has.
* ``delete_after_read`` makes the filesystem the checkpoint: a shipped span file is deleted,
  so "has everything been shipped?" is simply "are there any ``spans*.jsonl`` left?". The
  send queue is persisted via ``file_storage`` so a shipper restart never drops in-flight data.
"""

import asyncio
import logging
import os
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Final

import yaml
from aiodocker import Docker, DockerError
from aiodocker.types import JSONObject
from fastapi import FastAPI, status
from servicelib.fastapi.tracing import get_tracing_config
from servicelib.logging_utils import log_context
from settings_library.tracing import TracingSettings
from yarl import URL

from ..core.settings import ApplicationSettings, UserServicesTracingSettings
from .mounted_fs import MountedVolumes

_logger = logging.getLogger(__name__)

# span files written by the injected collector on the shared volume (live + size-rotated)
_TRACES_MOUNT_POINT: Final[str] = "/traces"
_SPANS_FILES_GLOB: Final[str] = "spans*.jsonl"
# the shipper's own bookkeeping (persistent send queue); kept off the spans glob
_SHIPPER_STATE_DIR: Final[str] = f"{_TRACES_MOUNT_POINT}/.trace-shipper-state"

_CONTAINER_NAME_SUFFIX: Final[str] = "otel-trace-shipper"
# own namespace ("otc" = octel trace shipper): keeps the shipper out of the dy-sidecar
# container namespace so it is never matched / reaped by dy-sidecar name-prefix lookups
_CONTAINER_NAME_PREFIX: Final[str] = "otc"
# Docker Engine API expresses a CPU-core quota as NanoCpus (cores * 1e9)
_NANO_CPUS_PER_CORE: Final[int] = 10**9
_DRAIN_POLL_INTERVAL: Final[timedelta] = timedelta(seconds=0.5)


@asynccontextmanager
async def _docker_client() -> AsyncIterator[Docker]:
    async with Docker() as client:
        yield client


def is_user_services_tracing_enabled(app: FastAPI) -> bool:
    settings: ApplicationSettings = app.state.settings
    tracing_config = get_tracing_config(app)
    return tracing_config.tracing_enabled and settings.DY_SIDECAR_USER_SERVICES_TRACING_OPT_IN


def _shipper_container_name(settings: ApplicationSettings) -> str:
    # deterministic so create / remove / any external reaper all agree on the name;
    # uses its own "otc" namespace (NOT the dy-sidecar one) to avoid name collisions
    return f"{_CONTAINER_NAME_PREFIX}-{settings.DY_SIDECAR_NODE_ID}-{_CONTAINER_NAME_SUFFIX}"


def _platform_otlp_traces_endpoint(platform_tracing_settings: TracingSettings) -> str:
    return str(
        URL(f"{platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}")
        .with_port(platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT)
        .with_path("/v1/traces")
    )


def _generate_shipper_config(platform_tracing_settings: TracingSettings) -> str:
    config = {
        "extensions": {
            "file_storage/shipper": {
                "directory": _SHIPPER_STATE_DIR,
                # create the state dir on first boot (it lives on the shared traces volume)
                "create_directory": True,
            },
        },
        "receivers": {
            "otlpjsonfile": {
                "include": [f"{_TRACES_MOUNT_POINT}/{_SPANS_FILES_GLOB}"],
                "start_at": "beginning",
                # deletes each span file once it has been shipped
                "delete_after_read": True,
            }
        },
        "exporters": {
            "otlp_http": {
                "traces_endpoint": _platform_otlp_traces_endpoint(platform_tracing_settings),
                "retry_on_failure": {"enabled": True},
                "sending_queue": {"enabled": True, "storage": "file_storage/shipper"},
            }
        },
        "service": {
            "extensions": ["file_storage/shipper"],
            "pipelines": {
                "traces": {
                    "receivers": ["otlpjsonfile"],
                    "exporters": ["otlp_http"],
                }
            },
        },
    }
    return yaml.safe_dump(config, default_flow_style=False)


def _build_shipper_container_config(
    *,
    settings: ApplicationSettings,
    user_services_tracing_settings: UserServicesTracingSettings,
    platform_tracing_settings: TracingSettings,
    traces_volume_bind: str,
) -> JSONObject:
    image = (
        f"{user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_IMAGE_NAME}:"
        f"{platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_IMAGE_VERSION}"
    )
    config_yaml = _generate_shipper_config(platform_tracing_settings)

    return {
        "Image": image,
        "User": f"{os.getuid()}:{os.getgid()}",
        # 'filelog.allowFileDeletion' gate is required by the otlpjsonfile receiver's
        # 'delete_after_read' option (filesystem is our shipped/not-shipped checkpoint)
        "Cmd": [
            "--config=env:OTEL_COLLECTOR_CONFIG",
            "--feature-gates=filelog.allowFileDeletion",
        ],
        "Env": [f"OTEL_COLLECTOR_CONFIG={config_yaml}"],
        "Labels": {
            "io.simcore.dynamic-sidecar.trace-shipper": "true",
            "io.simcore.service-run-id": f"{settings.DY_SIDECAR_RUN_ID}",
            "io.simcore.node-id": f"{settings.DY_SIDECAR_NODE_ID}",
        },
        "HostConfig": {
            "Binds": [traces_volume_bind],
            # share the sidecar's network namespace -> same DNS/egress to the platform
            "NetworkMode": f"container:{socket.gethostname()}",
            "RestartPolicy": {"Name": "unless-stopped"},
            # resource caps shared with the injected collector (Docker Engine API equivalents
            # of compose mem_limit/cpus/cpu_shares)
            "Memory": user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT,
            "NanoCpus": int(
                user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT * _NANO_CPUS_PER_CORE
            ),
            "CpuShares": user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_SHARES,
        },
    }


async def create_user_services_trace_collector(app: FastAPI) -> None:
    """Idempotently creates and starts the trace-shipper container.

    Called once the user services (and the injected collector writing the span files) are up.
    Safe to call repeatedly: if the container already exists it is left running.
    """
    settings: ApplicationSettings = app.state.settings
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    platform_tracing_settings = settings.DYNAMIC_SIDECAR_TRACING
    assert platform_tracing_settings is not None  # nosec

    container_name = _shipper_container_name(settings)
    traces_volume_bind = await mounted_volumes.get_traces_docker_volume(settings.DY_SIDECAR_RUN_ID)

    container_config = _build_shipper_container_config(
        settings=settings,
        user_services_tracing_settings=settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG,
        platform_tracing_settings=platform_tracing_settings,
        traces_volume_bind=traces_volume_bind,
    )

    with log_context(_logger, logging.INFO, f"create trace-shipper container '{container_name}'"):
        async with _docker_client() as client:
            try:
                await client.containers.run(config=container_config, name=container_name)
            except DockerError as e:
                if e.status == status.HTTP_409_CONFLICT:
                    # name already in use: shipper is already running -> idempotent no-op
                    _logger.info("trace-shipper '%s' already exists, leaving it running", container_name)
                    return
                raise


async def _drain_remaining_span_files(app: FastAPI) -> None:
    """Waits (bounded) until the shipper has shipped (and ``delete_after_read``-deleted) all
    span files, so nothing is lost when the shared volume is torn down."""
    settings: ApplicationSettings = app.state.settings
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    traces_path: Path = mounted_volumes.disk_traces_path
    timeout = settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG.USER_SERVICES_TRACING_DRAIN_TIMEOUT.total_seconds()

    async def _wait_until_shipped() -> None:
        while await asyncio.to_thread(lambda: list(traces_path.glob(_SPANS_FILES_GLOB))):  # noqa: ASYNC110
            await asyncio.sleep(_DRAIN_POLL_INTERVAL.total_seconds())

    try:
        await asyncio.wait_for(_wait_until_shipped(), timeout=timeout)
    except TimeoutError:
        _logger.warning("Trace-shipper drain timed out after %.1fs, some traces may be lost", timeout)


async def remove_user_services_trace_collector(app: FastAPI) -> None:
    """Idempotently drains and removes the trace-shipper container.

    Called when the user services are being removed. First waits (bounded) for the shipper to
    ship all remaining span files, then stops and deletes it. Safe to call when the container
    does not exist.
    """
    settings: ApplicationSettings = app.state.settings
    container_name = _shipper_container_name(settings)

    with log_context(_logger, logging.INFO, f"remove trace-shipper container '{container_name}'"):
        await _drain_remaining_span_files(app)

        async with _docker_client() as client:
            try:
                container = await client.containers.get(container_name)
            except DockerError as e:
                if e.status == status.HTTP_404_NOT_FOUND:
                    return  # already gone -> idempotent no-op
                raise

            try:
                await container.stop()  # SIGTERM: collector flushes its queue
            except DockerError as e:
                if e.status not in (status.HTTP_304_NOT_MODIFIED, status.HTTP_404_NOT_FOUND):
                    raise

            try:
                await container.delete(force=True)
            except DockerError as e:
                if e.status != status.HTTP_404_NOT_FOUND:
                    raise
