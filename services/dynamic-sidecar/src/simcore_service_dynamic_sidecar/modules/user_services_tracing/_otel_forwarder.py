"""The trace-forwarder container: reads OTLP-JSON span files from the shared ``/traces`` volume
and pushes them to the platform's OTLP/HTTP endpoint.

Lifecycle: created when user services start, removed when they stop (both idempotent).
Docker keeps it alive between those two events via ``RestartPolicy=unless-stopped``.
The send queue is persisted via ``file_storage`` so a forwarder restart never drops in-flight data.
"""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final

import yaml
from aiodocker import Docker, DockerError
from aiodocker.types import JSONObject
from fastapi import FastAPI, status
from servicelib.fastapi.tracing import get_tracing_config
from servicelib.logging_utils import log_context
from settings_library.tracing import TracingSettings
from yarl import URL

from ._settings import UserServicesTracingSettings

if TYPE_CHECKING:
    from ...core.settings import ApplicationSettings
    from ..mounted_fs import MountedVolumes

_logger = logging.getLogger(__name__)

# span files written by the injected collector on the shared volume (live + size-rotated)
_TRACES_MOUNT_POINT: Final[str] = "/traces"
_SPANS_FILES_GLOB: Final[str] = "spans*.jsonl"
# the forwarder's own bookkeeping (persistent send queue); kept off the spans glob
_FORWARDER_STATE_DIR: Final[str] = f"{_TRACES_MOUNT_POINT}/.trace-forwarder-state"
_FILE_STORAGE_EXTENSION_NAME: Final[str] = "file_storage/forwarder"

_CONTAINER_NAME_SUFFIX: Final[str] = "otel-trace-forwarder"
# own namespace ("otc" = octel trace forwarder): keeps the forwarder out of the dy-sidecar
# container namespace so it is never matched / reaped by dy-sidecar name-prefix lookups
_CONTAINER_NAME_PREFIX: Final[str] = "otc"
# Docker Engine API expresses a CPU-core quota as NanoCpus (cores * 1e9)
_NANO_CPUS_PER_CORE: Final[int] = 10**9


@asynccontextmanager
async def _docker_client() -> AsyncIterator[Docker]:
    async with Docker() as client:
        yield client


def is_user_services_tracing_enabled(app: FastAPI) -> bool:
    settings: ApplicationSettings = app.state.settings
    tracing_config = get_tracing_config(app)
    return tracing_config.tracing_enabled and settings.DY_SIDECAR_USER_SERVICES_TRACING_OPT_IN


def _forwarder_container_name(settings: ApplicationSettings) -> str:
    # deterministic so create / remove / any external reaper all agree on the name;
    # uses its own "otc" namespace (NOT the dy-sidecar one) to avoid name collisions
    return f"{_CONTAINER_NAME_PREFIX}-{settings.DY_SIDECAR_NODE_ID}-{_CONTAINER_NAME_SUFFIX}"


def _platform_otlp_traces_endpoint(platform_tracing_settings: TracingSettings) -> str:
    return str(
        URL(f"{platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT}")
        .with_port(platform_tracing_settings.TRACING_OPENTELEMETRY_COLLECTOR_PORT)
        .with_path("/v1/traces")
    )


def _generate_forwarder_config(platform_tracing_settings: TracingSettings) -> str:
    config = {
        "extensions": {
            _FILE_STORAGE_EXTENSION_NAME: {
                "directory": _FORWARDER_STATE_DIR,
                # create the state dir on first boot (it lives on the shared traces volume)
                "create_directory": True,
            },
        },
        "receivers": {
            "otlpjsonfile": {
                "include": [f"{_TRACES_MOUNT_POINT}/{_SPANS_FILES_GLOB}"],
                "start_at": "beginning",
                "storage": _FILE_STORAGE_EXTENSION_NAME,
            }
        },
        "exporters": {
            "otlp_http": {
                "traces_endpoint": _platform_otlp_traces_endpoint(platform_tracing_settings),
                "retry_on_failure": {"enabled": True},
                "sending_queue": {"enabled": True, "storage": _FILE_STORAGE_EXTENSION_NAME},
            }
        },
        "service": {
            "extensions": [_FILE_STORAGE_EXTENSION_NAME],
            "pipelines": {
                "traces": {
                    "receivers": ["otlpjsonfile"],
                    "exporters": ["otlp_http"],
                }
            },
        },
    }
    return yaml.safe_dump(config, default_flow_style=False)


def _build_forwarder_container_config(
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
    config_yaml = _generate_forwarder_config(platform_tracing_settings)

    return {
        "Image": image,
        "User": f"{os.getuid()}:{os.getgid()}",
        "Cmd": [
            "--config=env:OTEL_COLLECTOR_CONFIG",
        ],
        "Env": [f"OTEL_COLLECTOR_CONFIG={config_yaml}"],
        "Labels": {
            "io.simcore.dynamic-sidecar.trace-forwarder": "true",
            "io.simcore.service-run-id": f"{settings.DY_SIDECAR_RUN_ID}",
            "io.simcore.node-id": f"{settings.DY_SIDECAR_NODE_ID}",
        },
        "HostConfig": {
            "Binds": [traces_volume_bind],
            # share the sidecar's network namespace -> same DNS/egress to the platform
            "NetworkMode": f"container:{socket.gethostname()}",
            "RestartPolicy": {"Name": "unless-stopped"},
            # same resource caps as the injected collector (Docker Engine API equivalents
            # of compose mem_limit/cpus/cpu_shares)
            "Memory": user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT,
            "NanoCpus": int(
                user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT * _NANO_CPUS_PER_CORE
            ),
            "CpuShares": user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_SHARES,
        },
    }


async def create_user_services_trace_collector(app: FastAPI) -> None:
    """Idempotently creates and starts the trace-forwarder container.

    Called once the user services (and the injected collector writing the span files) are up.
    Safe to call repeatedly: if the container already exists it is left running.
    """
    settings: ApplicationSettings = app.state.settings
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    platform_tracing_settings = settings.DYNAMIC_SIDECAR_TRACING
    assert platform_tracing_settings is not None  # nosec

    container_name = _forwarder_container_name(settings)
    traces_volume_bind = await mounted_volumes.get_traces_docker_volume(settings.DY_SIDECAR_RUN_ID)

    container_config = _build_forwarder_container_config(
        settings=settings,
        user_services_tracing_settings=settings.DYNAMIC_SIDECAR_USER_SERVICES_TRACING_CONFIG,
        platform_tracing_settings=platform_tracing_settings,
        traces_volume_bind=traces_volume_bind,
    )

    with log_context(_logger, logging.INFO, f"create trace-forwarder container '{container_name}'"):
        async with _docker_client() as client:
            try:
                await client.containers.run(config=container_config, name=container_name)
            except DockerError as e:
                if e.status == status.HTTP_409_CONFLICT:
                    _logger.info("trace-forwarder '%s' already exists, leaving it running", container_name)
                    return
                raise


async def remove_user_services_trace_collector(app: FastAPI) -> None:
    """Idempotently stops and removes the trace-forwarder container."""
    settings: ApplicationSettings = app.state.settings
    container_name = _forwarder_container_name(settings)

    with log_context(_logger, logging.INFO, f"remove trace-forwarder container '{container_name}'"):
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
